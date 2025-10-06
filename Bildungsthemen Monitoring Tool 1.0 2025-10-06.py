# Bildungsthemen Monitoring Tool
# Ueberwacht kontinuierlich Entwicklungen in der Bildungslandschaft

import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import time
import schedule
from collections import defaultdict
import sqlite3
from dataclasses import dataclass, asdict
from typing import List, Dict
import re

@dataclass
class BildungsNews:
    titel: str
    quelle: str
    url: str
    datum: str
    kategorie: str
    zusammenfassung: str
    schlagworte: List[str]

class BildungsMonitor:
    def __init__(self, db_path="bildung_monitor.db"):
        self.db_path = db_path
        self.init_database()
        
        # Wichtige Bildungsthemen-Kategorien
        self.kategorien = {
            'digitalisierung': ['digitalisierung', 'digital', 'edtech', 'lernplattform', 'e-learning', 'online-lernen'],
            'ki_bildung': ['ki', 'kuenstliche intelligenz', 'chatgpt', 'ai', 'machine learning', 'algorithmen', 'ki-tools', 'automatisierung'],
            'inklusion': ['inklusion', 'integration', 'diversitaet', 'chancengleichheit', 'barrierefrei', 'teilhabe'],
            'hochschule': ['universitaet', 'hochschule', 'studium', 'forschung', 'bachelor', 'master', 'promotion'],
            'berufsbildung': ['ausbildung', 'berufsschule', 'duales system', 'lehre', 'azubi', 'berufliche bildung'],
            'erwachsenenbildung': ['volkshochschule', 'vhs', 'weiterbildung', 'erwachsenenbildung', 'keb', 
                                   'evangelische bildung', 'lebenslanges lernen', 'fortbildung', 'fernstudium', 'bildungsurlaub'],
            'forschung_eb': ['erwachsenenbildungsforschung', 'bildungsforschung', 'paedagogische forschung', 'didaktik', 
                            'lernforschung', 'empirische bildungsforschung', 'bildungswissenschaft'],
            'nachhaltigkeit': ['nachhaltigkeit', 'klimaschutz', 'umweltbildung', 'bne', 'bildung nachhaltige entwicklung',
                              'oekologie', 'klimawandel', 'ressourcen', 'agenda 2030', '17 ziele'],
            'interreligioser_dialog': ['interreligioes', 'dialog der religionen', 'oekumene', 'religionen', 'weltreligionen',
                                       'interkulturelles', 'religionsuebergreifend', 'abrahamitische religionen', 'toleranz'],
            'foerdermittel': ['foerderung', 'foerdermittel', 'finanzierung', 'zuschuss', 'projektfoerderung', 'bildungsfoerderung',
                             'eu-foerderung', 'bundesmittel', 'landesfoerderung', 'stiftung', 'erasmus', 'antrag'],
            'spiritualitaet': ['spiritualitaet', 'meditation', 'achtsamkeit', 'kontemplation', 'exerzitien', 'geistliches leben',
                              'besinnung', 'innere entwicklung', 'sinnfragen', 'lebenskunst'],
            'familienbildung': ['familienbildung', 'elternbildung', 'erziehung', 'familien', 'eltern-kind', 'familienstaette',
                               'elternkurs', 'paarberatung', 'familienzentrum', 'muetter', 'vaeter'],
            'maennerarbeit': ['maennerarbeit', 'maennerbildung', 'vaeterbildung', 'maennlichkeit', 'gender male',
                             'maennergruppe', 'vaetergruppe', 'new masculinity'],
            'frauenarbeit': ['frauenbildung', 'frauenarbeit', 'gender', 'gleichstellung', 'empowerment frauen',
                            'frauengruppe', 'feminismus', 'maedchenarbeit', 'women empowerment'],
            'seniorenarbeit': ['seniorenbildung', 'altenbildung', 'senioren', 'alter', 'generationen', 'lebensaeltere',
                              'altersbildung', '50plus', 'rentenalter', 'demografie', 'generationengerechtigkeit']
        }
        
        # RSS-Feeds wichtiger Bildungsquellen
        self.rss_feeds = [
            'https://www.bildungsserver.de/news.rss',
            'https://www.news4teachers.de/feed/',
            'https://deutsches-schulportal.de/feed/',
            'https://www.bildungsspiegel.de/feed/',
            'https://www.wissenschaft.de/feed/',
            'https://www.bibb.de/de/pressemitteilungen_3.rss',
            'https://www.e-teaching.org/news/rss',
            'https://www.die-bonn.de/id/37623/rss.xml',
        ]
        
        # Google News RSS fuer Erwachsenenbildung
        self.google_news_feeds = [
            'https://news.google.com/rss/search?q=Volkshochschule+OR+VHS+when:7d&hl=de&gl=DE&ceid=DE:de',
            'https://news.google.com/rss/search?q="katholische+erwachsenenbildung"+OR+KEB+when:7d&hl=de&gl=DE&ceid=DE:de',
            'https://news.google.com/rss/search?q="evangelische+erwachsenenbildung"+when:7d&hl=de&gl=DE&ceid=DE:de',
            'https://news.google.com/rss/search?q=Weiterbildung+Deutschland+when:7d&hl=de&gl=DE&ceid=DE:de',
        ]
        
        # Websites fuer Web-Scraping
        self.scrape_urls = [
            'https://www.keb-deutschland.de/aktuelles/',
            'https://www.dvv-vhs.de/startseite/',
            'https://www.deae.de/startseite/',
        ]
        
    def init_database(self):
        """Initialisiert die SQLite-Datenbank"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS nachrichten (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titel TEXT,
                quelle TEXT,
                url TEXT UNIQUE,
                datum TEXT,
                kategorie TEXT,
                zusammenfassung TEXT,
                schlagworte TEXT,
                erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
    
    def kategorisiere(self, text: str) -> str:
        """Kategorisiert einen Text basierend auf Schlagworten"""
        text_lower = text.lower()
        scores = defaultdict(int)
        
        for kategorie, begriffe in self.kategorien.items():
            for begriff in begriffe:
                if begriff in text_lower:
                    scores[kategorie] += 1
        
        if scores:
            return max(scores, key=scores.get)
        return 'allgemein'
    
    def extrahiere_schlagworte(self, text: str) -> List[str]:
        """Extrahiert relevante Schlagworte aus dem Text"""
        schlagworte = set()
        text_lower = text.lower()
        
        for kategorie_begriffe in self.kategorien.values():
            for begriff in kategorie_begriffe:
                if begriff in text_lower:
                    schlagworte.add(begriff)
        
        return list(schlagworte)[:5]
    
    def hole_rss_feeds(self) -> List[BildungsNews]:
        """Liest RSS-Feeds aus und extrahiert Nachrichten"""
        alle_news = []
        
        # Standard RSS-Feeds
        all_feeds = self.rss_feeds + self.google_news_feeds
        
        for feed_url in all_feeds:
            try:
                feed = feedparser.parse(feed_url)
                
                for entry in feed.entries[:10]:
                    titel = entry.get('title', '')
                    zusammenfassung = entry.get('summary', entry.get('description', ''))
                    url = entry.get('link', '')
                    
                    # Datum parsen mit Fehlerbehandlung
                    try:
                        if hasattr(entry, 'published_parsed') and entry.published_parsed:
                            datum = time.strftime('%Y-%m-%d', entry.published_parsed)
                        elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                            datum = time.strftime('%Y-%m-%d', entry.updated_parsed)
                        else:
                            datum = datetime.now().strftime('%Y-%m-%d')
                    except (TypeError, ValueError):
                        datum = datetime.now().strftime('%Y-%m-%d')
                    
                    # Kategorie und Schlagworte ermitteln
                    volltext = f"{titel} {zusammenfassung}"
                    kategorie = self.kategorisiere(volltext)
                    schlagworte = self.extrahiere_schlagworte(volltext)
                    
                    news = BildungsNews(
                        titel=titel,
                        quelle=feed.feed.get('title', feed_url),
                        url=url,
                        datum=datum,
                        kategorie=kategorie,
                        zusammenfassung=zusammenfassung[:200],
                        schlagworte=schlagworte
                    )
                    alle_news.append(news)
                    
            except Exception as e:
                print(f"Fehler beim Abrufen von {feed_url}: {e}")
        
        return alle_news
    
    def scrape_website(self, url: str) -> List[BildungsNews]:
        """Scraped Nachrichten von einer Website"""
        alle_news = []
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            # SSL-Verifizierung deaktivieren falls noetig und Timeout erhoehen
            response = requests.get(url, headers=headers, timeout=15, verify=True)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Suche nach haeufigen News-Elementen
            news_elements = soup.find_all(['article', 'div'], class_=re.compile('news|article|post|aktuell', re.I))
            
            for element in news_elements[:10]:
                titel_tag = element.find(['h1', 'h2', 'h3', 'h4', 'a'])
                if not titel_tag:
                    continue
                
                titel = titel_tag.get_text(strip=True)
                if not titel or len(titel) < 10:
                    continue
                
                # URL extrahieren
                link_tag = element.find('a', href=True)
                artikel_url = link_tag['href'] if link_tag else url
                if artikel_url.startswith('/'):
                    from urllib.parse import urljoin
                    artikel_url = urljoin(url, artikel_url)
                
                # Zusammenfassung
                text_tag = element.find(['p', 'div'], class_=re.compile('text|beschreibung|summary|excerpt', re.I))
                zusammenfassung = text_tag.get_text(strip=True)[:200] if text_tag else ''
                
                # Datum
                datum = datetime.now().strftime('%Y-%m-%d')
                
                volltext = f"{titel} {zusammenfassung}"
                kategorie = self.kategorisiere(volltext)
                schlagworte = self.extrahiere_schlagworte(volltext)
                
                news = BildungsNews(
                    titel=titel,
                    quelle=url,
                    url=artikel_url,
                    datum=datum,
                    kategorie=kategorie,
                    zusammenfassung=zusammenfassung,
                    schlagworte=schlagworte
                )
                alle_news.append(news)
                
        except requests.exceptions.SSLError:
            # Bei SSL-Problemen mit verify=False versuchen
            try:
                response = requests.get(url, headers=headers, timeout=15, verify=False)
                print(f"Warnung: SSL-Verifizierung deaktiviert fuer {url}")
                # Rest des Codes wuerde hier folgen, aber wir loggen nur
            except Exception as e:
                print(f"Fehler beim Scrapen von {url}: SSL-Problem konnte nicht umgangen werden")
        except requests.exceptions.Timeout:
            print(f"Timeout beim Scrapen von {url}")
        except Exception as e:
            print(f"Fehler beim Scrapen von {url}: {e}")
        
        return alle_news
    
    def hole_alle_news(self) -> List[BildungsNews]:
        """Sammelt News aus allen Quellen (RSS + Scraping)"""
        alle_news = []
        
        # RSS-Feeds
        print("Hole RSS-Feeds...")
        alle_news.extend(self.hole_rss_feeds())
        
        # Web-Scraping
        print("Scrape Websites...")
        for url in self.scrape_urls:
            alle_news.extend(self.scrape_website(url))
        
        return alle_news
    
    def speichere_news(self, news_liste: List[BildungsNews]):
        """Speichert neue Nachrichten in der Datenbank"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        neu_hinzugefuegt = 0
        for news in news_liste:
            try:
                c.execute('''
                    INSERT INTO nachrichten 
                    (titel, quelle, url, datum, kategorie, zusammenfassung, schlagworte)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    news.titel,
                    news.quelle,
                    news.url,
                    news.datum,
                    news.kategorie,
                    news.zusammenfassung,
                    json.dumps(news.schlagworte)
                ))
                neu_hinzugefuegt += 1
            except sqlite3.IntegrityError:
                pass
        
        conn.commit()
        conn.close()
        
        return neu_hinzugefuegt
        """Speichert neue Nachrichten in der Datenbank"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        neu_hinzugefuegt = 0
        for news in news_liste:
            try:
                c.execute('''
                    INSERT INTO nachrichten 
                    (titel, quelle, url, datum, kategorie, zusammenfassung, schlagworte)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    news.titel,
                    news.quelle,
                    news.url,
                    news.datum,
                    news.kategorie,
                    news.zusammenfassung,
                    json.dumps(news.schlagworte)
                ))
                neu_hinzugefuegt += 1
            except sqlite3.IntegrityError:
                pass
        
        conn.commit()
        conn.close()
        
        return neu_hinzugefuegt
    
    def erstelle_bericht(self, tage: int = 7) -> Dict:
        """Erstellt einen Bericht ueber die letzten N Tage"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        datum_von = (datetime.now() - timedelta(days=tage)).strftime('%Y-%m-%d')
        
        c.execute('''
            SELECT kategorie, COUNT(*) 
            FROM nachrichten 
            WHERE datum >= ?
            GROUP BY kategorie
            ORDER BY COUNT(*) DESC
        ''', (datum_von,))
        
        kategorien_stats = dict(c.fetchall())
        
        # Alle definierten Kategorien mit 0 initialisieren
        alle_kategorien = {kat: 0 for kat in self.kategorien.keys()}
        alle_kategorien['allgemein'] = 0
        
        # Vorhandene Werte ueberschreiben
        for kat, anzahl in kategorien_stats.items():
            if kat in alle_kategorien:
                alle_kategorien[kat] = anzahl
            elif kat == 'allgemein':
                alle_kategorien['allgemein'] = anzahl
        
        c.execute('''
            SELECT titel, quelle, url, datum, kategorie
            FROM nachrichten
            WHERE datum >= ?
            ORDER BY datum DESC
            LIMIT 20
        ''', (datum_von,))
        
        top_news = c.fetchall()
        
        conn.close()
        
        return {
            'zeitraum': f'Letzte {tage} Tage',
            'kategorien': alle_kategorien,
            'anzahl_gesamt': sum(alle_kategorien.values()),
            'top_nachrichten': top_news
        }
    
    def suche_thema(self, suchbegriff: str, limit: int = 10) -> List[Dict]:
        """Sucht nach einem bestimmten Thema"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            SELECT titel, quelle, url, datum, kategorie, zusammenfassung
            FROM nachrichten
            WHERE titel LIKE ? OR zusammenfassung LIKE ?
            ORDER BY datum DESC
            LIMIT ?
        ''', (f'%{suchbegriff}%', f'%{suchbegriff}%', limit))
        
        ergebnisse = []
        for row in c.fetchall():
            ergebnisse.append({
                'titel': row[0],
                'quelle': row[1],
                'url': row[2],
                'datum': row[3],
                'kategorie': row[4],
                'zusammenfassung': row[5]
            })
        
        conn.close()
        return ergebnisse
    
    def starte_monitoring(self, intervall_minuten: int = 60):
        """Startet das kontinuierliche Monitoring"""
        def monitoring_job():
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starte Monitoring...")
            news = self.hole_alle_news()
            neu = self.speichere_news(news)
            print(f"-> {neu} neue Nachrichten hinzugefuegt")
        
        monitoring_job()
        
        schedule.every(intervall_minuten).minutes.do(monitoring_job)
        
        print(f"\nMonitoring laeuft (alle {intervall_minuten} Minuten)")
        print("Druecke Ctrl+C zum Beenden\n")
        
        while True:
            schedule.run_pending()
            time.sleep(1)


# Beispiel-Nutzung
if __name__ == "__main__":
    monitor = BildungsMonitor()
    
    print("Hole aktuelle Bildungsnachrichten...")
    news = monitor.hole_alle_news()
    neu = monitor.speichere_news(news)
    print(f"{neu} neue Nachrichten gespeichert\n")
    
    # Benutzerabfrage fuer Berichtszeitraum
    print("="*80)
    while True:
        try:
            tage_input = input("Fuer wie viele Tage soll der Bericht erstellt werden? (Standard: 7): ").strip()
            if tage_input == "":
                anzahl_tage = 7
            else:
                anzahl_tage = int(tage_input)
                if anzahl_tage < 1:
                    print("Bitte eine positive Zahl eingeben!")
                    continue
            break
        except ValueError:
            print("Bitte eine gueltige Zahl eingeben!")
    
    bericht = monitor.erstelle_bericht(tage=anzahl_tage)
    print(f"\nBericht: {bericht['zeitraum']}")
    print(f"Gesamt: {bericht['anzahl_gesamt']} Nachrichten\n")
    
    print("="*80)
    print("NACHRICHTEN PRO KATEGORIE")
    print("="*80)
    
    # Kategorien mit Treffern
    for kat, anzahl in sorted(bericht['kategorien'].items(), key=lambda x: x[1], reverse=True):
        if anzahl > 0:
            print(f"\n### {kat.upper()} ({anzahl} Nachrichten) ###")
            print("-"*80)
            
            # Hole alle Nachrichten dieser Kategorie
            conn = sqlite3.connect(monitor.db_path)
            c = conn.cursor()
            datum_von = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            c.execute('''
                SELECT titel, quelle, url, datum
                FROM nachrichten
                WHERE kategorie = ? AND datum >= ?
                ORDER BY datum DESC
            ''', (kat, datum_von))
            
            nachrichten = c.fetchall()
            conn.close()
            
            for i, (titel, quelle, url, datum) in enumerate(nachrichten, 1):
                print(f"{i}. {titel}")
                print(f"   Quelle: {quelle} | Datum: {datum}")
                print(f"   URL: {url}")
                print()
    
    print("\n" + "="*80)
    print("KATEGORIEN OHNE TREFFER")
    print("="*80)
    for kat, anzahl in sorted(bericht['kategorien'].items()):
        if anzahl == 0:
            print(f"  - {kat}")
    
    # Fuer kontinuierliches Monitoring:
    # monitor.starte_monitoring(intervall_minuten=60)