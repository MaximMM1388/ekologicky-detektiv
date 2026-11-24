"""Ekologický detektív — triedny kvíz pre lokálnu sieť alebo online hosting.
Bez externých knižníc; cloudový režim: EKO_CLOUD=1 a EKO_ADMIN_PIN=8-12 číslic.
"""
from __future__ import annotations

import hmac
import json
import os
import random
import re
import secrets
import socket
import sqlite3
import threading
import time
import webbrowser
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

BASE = Path(__file__).resolve().parent
STATIC = BASE / 'static'
CLOUD = os.environ.get('EKO_CLOUD') == '1'
DB = Path(os.environ.get('EKO_DB_PATH', '/tmp/eko_quiz.db' if CLOUD else str(BASE / 'quiz.db')))
SETTINGS = BASE / 'nastavenia.json'
PORT = int(os.environ.get('PORT', os.environ.get('EKO_PORT', '8765')))
DB_LOCK = threading.RLock()
ADMIN_SESSIONS: set[str] = set()
FAILED_LOGINS: dict[str, list[float]] = defaultdict(list)
ALLOWED_TEAMS = ('Jednotlivec', 'Tím A', 'Tím B', 'Tím C', 'Tím D', 'Tím E')

QUESTIONS = [
    {
        'id': 1, 'tag': 'Prenos energie', 'difficulty': 'Ľahká',
        'title': 'Ak má úroveň trávy 10 000 J, koľko energie zostane podľa modelu 10 % na úrovni hadov?',
        'context': 'Tráva → kobylka → žaba → had',
        'options': ['1 000 J', '100 J', '10 J', '1 J'], 'correct': 2,
        'explanation': '10 000 → 1 000 → 100 → 10 J. Na každej úrovni sme použili zjednodušený 10 % prenos.'
    },
    {
        'id': 2, 'tag': 'Pochopenie 10 %', 'difficulty': 'Stredná',
        'title': 'Čo znamená približné pravidlo 10 %?',
        'context': 'Vyber odborne najpresnejšie vysvetlenie.',
        'options': [
            'Zajac zje iba 10 % dostupnej trávy.',
            'Približne 10 % energie jednej úrovne sa prenesie do produkcie biomasy ďalšej úrovne.',
            'Zvyšných 90 % energie prestane existovať.',
            'Každý organizmus využije presne 10 % svojej potravy.'
        ], 'correct': 1,
        'explanation': 'Zvieratá prijímajú energiu potravou, ale mnoho energie spotrebujú pri životných procesoch a časť zostane v odpade.'
    },
    {
        'id': 3, 'tag': 'Producenti', 'difficulty': 'Ľahká',
        'title': 'Ktorý z nasledujúcich organizmov je producent?',
        'context': 'Producent vytvára organické látky z anorganických.',
        'options': ['Kobylka', 'Zelená riasa', 'Žaba', 'Líška'], 'correct': 1,
        'explanation': 'Zelené riasy využívajú fotosyntézu a vytvárajú organické látky. Živočíchy sú konzumenti.'
    },
    {
        'id': 4, 'tag': 'Tok energie', 'difficulty': 'Stredná',
        'title': 'Prečo energia v ekosystéme nekoluje ako voda alebo uhlík?',
        'context': 'Zamysli sa nad teplom a využiteľnosťou energie.',
        'options': [
            'Pretože energia pri dýchaní úplne zaniká.',
            'Pretože slnečné svetlo sa nikdy nemôže zachytiť.',
            'Pretože sa energia rozptyľuje ako teplo a samovoľne sa nevracia do potravového reťazca.',
            'Pretože rozkladače nič nevracajú do prostredia.'
        ], 'correct': 2,
        'explanation': 'Energia sa zachováva, ale rozptýlené teplo už nemá rovnakú využiteľnosť. Látky sa pritom môžu recyklovať.'
    },
    {
        'id': 5, 'tag': 'Ekologická situácia', 'difficulty': 'Stredná',
        'title': 'Sucho zníži dostupnú energiu trávy na polovicu. Koľko J zostane na úrovni hada?',
        'context': 'Pôvodne 10 000 J v tráve. Predpokladaj rovnaký 10 % prenos pri každom kroku.',
        'options': ['50 J', '5 J', '100 J', '500 J'], 'correct': 1,
        'explanation': '5 000 → 500 → 50 → 5 J. Je to model, nie presná predpoveď fungovania skutočného ekosystému.'
    },
    {
        'id': 6, 'tag': 'Ekologická pyramída', 'difficulty': 'Stredná',
        'title': 'Ktoré tvrdenie o ekologických pyramídach je správne?',
        'context': 'Porovnaj energiu, biomasu a početnosť.',
        'options': [
            'Energetická pyramída môže byť obrátená.',
            'Pyramída biomasy je vždy rovnaká ako pyramída početnosti.',
            'Energetická pyramída sa smerom nahor zužuje; ostatné pyramídy môžu mať aj obrátený tvar.',
            'Všetky pyramídy majú vždy rovnakú šírku.'
        ], 'correct': 2,
        'explanation': 'Energia dostupná ďalšej trofickej úrovni klesá, preto energetická pyramída nie je obrátená.'
    },
]


def connect():
    conn = sqlite3.connect(str(DB), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def new_code():
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return ''.join(secrets.choice(alphabet) for _ in range(5))


def init():
    if CLOUD:
        cloud_pin = os.environ.get('EKO_ADMIN_PIN', '')
        if not re.fullmatch(r'[0-9]{8,12}', cloud_pin):
            raise RuntimeError('Pre online rezim nastav EKO_ADMIN_PIN na 8 az 12 cislic v hostingu (secret environment variable).')
        cfg = {'admin_pin': cloud_pin}
    elif SETTINGS.exists():
        cfg = json.loads(SETTINGS.read_text('utf-8'))
    else:
        cfg = {'admin_pin': ''.join(str(secrets.randbelow(10)) for _ in range(6))}
        SETTINGS.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), 'utf-8')
    with DB_LOCK, connect() as db:
        db.executescript('''
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS players (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              nickname TEXT NOT NULL, team TEXT NOT NULL,
              token TEXT NOT NULL UNIQUE, joined_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS answers (
              player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
              question_id INTEGER NOT NULL, selected INTEGER NOT NULL,
              correct INTEGER NOT NULL, answered_at REAL NOT NULL,
              PRIMARY KEY(player_id,question_id)
            );
        ''')
        db.execute('INSERT OR IGNORE INTO meta(key,value) VALUES(?,?)', ('code', new_code()))
        db.execute('INSERT OR IGNORE INTO meta(key,value) VALUES(?,?)', ('status', 'waiting'))
        db.commit()
    return str(cfg['admin_pin'])

ADMIN_PIN = init()


def meta(db, key):
    row = db.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
    return row['value'] if row else None


def set_meta(db, key, val):
    db.execute('INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, str(val)))


def public_q(q):
    return {k: v for k, v in q.items() if k not in ('correct', 'explanation')}


def get_player(db, token):
    if not token or len(token) > 160:
        return None
    return db.execute('SELECT * FROM players WHERE token=?', (token,)).fetchone()


def get_player_state(db, player):
    own = db.execute('SELECT question_id, selected, correct, answered_at FROM answers WHERE player_id=? ORDER BY question_id', (player['id'],)).fetchall()
    return {
        'status': meta(db, 'status'),
        'player': {'nickname': player['nickname'], 'team': player['team'], 'joined_at': player['joined_at']},
        'answers': [
            {'question_id': a['question_id'], 'selected': a['selected'], 'correct': bool(a['correct']),
             'correct_index': QUESTIONS[a['question_id']-1]['correct'],
             'explanation': QUESTIONS[a['question_id']-1]['explanation'],
             'answered_at': a['answered_at']}
            for a in own
        ],
    }


def get_stats(db):
    rows = db.execute('''
        SELECT p.id, p.nickname, p.team, p.joined_at,
               a.question_id, a.selected, a.correct, a.answered_at
          FROM players p LEFT JOIN answers a ON a.player_id=p.id
         ORDER BY p.joined_at ASC, a.question_id ASC
    ''').fetchall()
    participants = {}
    for r in rows:
        if r['id'] not in participants:
            participants[r['id']] = {
                'nickname': r['nickname'], 'team': r['team'], 'joined_at': r['joined_at'],
                'answers': {}, 'correct_count': 0, 'answered_count': 0, 'score': 0, 'duration_sec': None
            }
        p = participants[r['id']]
        if r['question_id'] is not None:
            q = QUESTIONS[r['question_id']-1]
            p['answers'][str(r['question_id'])] = {
                'selected': r['selected'], 'option': q['options'][r['selected']],
                'correct': bool(r['correct']), 'answered_at': r['answered_at'],
            }
            p['answered_count'] += 1
            p['correct_count'] += int(r['correct'])
            p['last_answer_at'] = r['answered_at']
    for p in participants.values():
        p['score'] = p['correct_count'] * 100
        p['duration_sec'] = round(max(0, p.get('last_answer_at', p['joined_at']) - p['joined_at']), 1) if p['answered_count'] else None
        p['completed'] = p['answered_count'] == len(QUESTIONS)
        p.pop('last_answer_at', None)
    people = sorted(participants.values(), key=lambda p: (-p['score'], -p['answered_count'], p['duration_sec'] if p['duration_sec'] is not None else 1e10, p['nickname'].lower()))
    q_stats = []
    for q in QUESTIONS:
        counts = [0] * len(q['options'])
        for p in people:
            a = p['answers'].get(str(q['id']))
            if a:
                counts[a['selected']] += 1
        q_stats.append({
            'id': q['id'], 'tag': q['tag'], 'title': q['title'], 'options': q['options'],
            'correct_index': q['correct'], 'counts': counts, 'answered': sum(counts),
            'correct_count': counts[q['correct']],
        })
    teams = {}
    for p in people:
        if p['team'] == 'Jednotlivec':
            continue
        t = teams.setdefault(p['team'], {'name': p['team'], 'players': 0, 'score_sum': 0, 'correct_sum': 0})
        t['players'] += 1
        t['score_sum'] += p['score']
        t['correct_sum'] += p['correct_count']
    for t in teams.values():
        t['average_score'] = round(t['score_sum'] / t['players'])
    total_answers = sum(p['answered_count'] for p in people)
    total_correct = sum(p['correct_count'] for p in people)
    return {
        'code': meta(db, 'code'), 'status': meta(db, 'status'), 'questions_count': len(QUESTIONS),
        'players_count': len(people), 'completed_count': sum(p['completed'] for p in people),
        'total_answers': total_answers, 'accuracy': round(100 * total_correct / total_answers) if total_answers else 0,
        'players': people, 'question_stats': q_stats,
        'teams': sorted(teams.values(), key=lambda t: -t['average_score']),
        'updated_at': time.time(),
        'join_urls': [] if CLOUD else [f'http://{ip}:{PORT}/?kod={meta(db, "code")}' for ip in get_lan_addresses()],
    }


class Handler(BaseHTTPRequestHandler):
    server_version = 'EkoDetektiv/1.0'

    def log_message(self, fmt, *args):
        # Nezapisujeme mená ani odpovede do prístupového logu.
        if not self.path.startswith('/api/'):
            super().log_message(fmt, *args)

    def send_json(self, obj, code=200):
        payload = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(payload)

    def problem(self, message, code=400):
        self.send_json({'error': message}, code)

    def send_file(self, filename, content_type):
        path = STATIC / filename
        if not path.is_file():
            return self.problem('Súbor neexistuje.', 404)
        content = path.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(content)

    def read_body(self):
        try:
            n = int(self.headers.get('Content-Length', 0))
            if n <= 0 or n > 12000:
                return None
            return json.loads(self.rfile.read(n).decode('utf-8'))
        except (ValueError, UnicodeError, json.JSONDecodeError):
            return None

    def bearer(self):
        a = self.headers.get('Authorization', '')
        return a[7:] if a.startswith('Bearer ') else ''

    def is_admin(self):
        token = self.bearer()
        return token in ADMIN_SESSIONS if token else False

    def do_GET(self):
        route = urlparse(self.path).path
        if route in ('/', '/admin', '/index.html'):
            return self.send_file('index.html', 'text/html; charset=utf-8')
        if route == '/styles.css':
            return self.send_file('styles.css', 'text/css; charset=utf-8')
        if route == '/app.js':
            return self.send_file('app.js', 'application/javascript; charset=utf-8')
        if route == '/api/public':
            with DB_LOCK, connect() as db:
                return self.send_json({'status': meta(db, 'status'), 'questions_count': len(QUESTIONS)})
        if route == '/api/questions':
            return self.send_json({'questions': [public_q(q) for q in QUESTIONS]})
        if route == '/api/player/state':
            with DB_LOCK, connect() as db:
                p = get_player(db, self.bearer())
                if not p:
                    return self.problem('Hráč sa nenašiel. Pripoj sa znova.', 401)
                return self.send_json(get_player_state(db, p))
        if route == '/api/admin/stats':
            if not self.is_admin():
                return self.problem('Prístup iba pre autora.', 401)
            with DB_LOCK, connect() as db:
                return self.send_json(get_stats(db))
        self.problem('Neznáma adresa.', 404)

    def do_POST(self):
        route = urlparse(self.path).path
        body = self.read_body()
        if not isinstance(body, dict):
            return self.problem('Neplatná požiadavka.')
        if route == '/api/admin/login':
            key = self.client_address[0]
            now = time.time()
            FAILED_LOGINS[key] = [a for a in FAILED_LOGINS[key] if now - a < 60]
            if len(FAILED_LOGINS[key]) >= 8:
                return self.problem('Priveľa pokusov. Skús neskôr.', 429)
            if not hmac.compare_digest(str(body.get('pin', '')), ADMIN_PIN):
                FAILED_LOGINS[key].append(now)
                return self.problem('Nesprávny autorský PIN.', 401)
            token = secrets.token_urlsafe(32)
            ADMIN_SESSIONS.add(token)
            return self.send_json({'admin_token': token})
        if route == '/api/join':
            nickname = str(body.get('nickname', '')).strip()
            team = str(body.get('team', 'Jednotlivec')).strip()
            code = str(body.get('code', '')).strip().upper()
            if not 2 <= len(nickname) <= 24 or any(ord(ch) < 32 for ch in nickname):
                return self.problem('Prezývka musí mať 2 až 24 znakov.')
            if team not in ALLOWED_TEAMS:
                return self.problem('Neplatný tím.')
            with DB_LOCK, connect() as db:
                if meta(db, 'status') != 'running':
                    return self.problem('Autor zatiaľ kvíz nespustil.')
                if not hmac.compare_digest(code, meta(db, 'code')):
                    return self.problem('Nesprávny kód miestnosti.')
                existing = db.execute('SELECT 1 FROM players WHERE nickname=? COLLATE NOCASE', (nickname,)).fetchone()
                if existing:
                    return self.problem('Táto prezývka je už obsadená. Vyber inú.')
                token = secrets.token_urlsafe(32)
                db.execute('INSERT INTO players(nickname,team,token,joined_at) VALUES(?,?,?,?)', (nickname, team, token, time.time()))
                db.commit()
                return self.send_json({'player_token': token})
        if route == '/api/answer':
            try:
                qid = int(body.get('question_id'))
                selected = int(body.get('selected'))
            except (ValueError, TypeError):
                return self.problem('Neplatná odpoveď.')
            if not 1 <= qid <= len(QUESTIONS) or not 0 <= selected < len(QUESTIONS[qid-1]['options']):
                return self.problem('Neplatná odpoveď.')
            with DB_LOCK, connect() as db:
                p = get_player(db, self.bearer())
                if not p:
                    return self.problem('Nie si prihlásený.', 401)
                if meta(db, 'status') != 'running':
                    return self.problem('Kvíz je pozastavený alebo ukončený.')
                answered = db.execute('SELECT question_id FROM answers WHERE player_id=? ORDER BY question_id', (p['id'],)).fetchall()
                if qid != len(answered) + 1:
                    return self.problem('Odpovedz na otázky postupne. Odpoveď nemožno zmeniť.')
                correct = int(selected == QUESTIONS[qid-1]['correct'])
                db.execute('INSERT INTO answers(player_id,question_id,selected,correct,answered_at) VALUES(?,?,?,?,?)', (p['id'], qid, selected, correct, time.time()))
                db.commit()
                return self.send_json(get_player_state(db, p))
        if route.startswith('/api/admin/'):
            if not self.is_admin():
                return self.problem('Prístup iba pre autora.', 401)
            with DB_LOCK, connect() as db:
                if route == '/api/admin/status':
                    status = body.get('status')
                    if status not in ('waiting', 'running', 'closed'):
                        return self.problem('Neplatný stav.')
                    set_meta(db, 'status', status)
                    db.commit()
                    return self.send_json(get_stats(db))
                if route == '/api/admin/reset':
                    db.execute('DELETE FROM answers')
                    db.execute('DELETE FROM players')
                    db.execute("DELETE FROM sqlite_sequence WHERE name='players'")
                    set_meta(db, 'code', new_code())
                    set_meta(db, 'status', 'waiting')
                    db.commit()
                    return self.send_json(get_stats(db))
        self.problem('Neznáma požiadavka.', 404)


def get_lan_addresses():
    addresses = set()
    try:
        hostname = socket.gethostname()
        for entry in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = entry[4][0]
            if not ip.startswith('127.') and not ip.startswith('169.254.'):
                addresses.add(ip)
    except OSError:
        pass
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(('192.0.2.1', 9))  # iba zistenie rozhrania, bez odosielania dát
        ip = sock.getsockname()[0]
        sock.close()
        if ip and not ip.startswith('127.'):
            addresses.add(ip)
    except OSError:
        pass
    return sorted(addresses)


def run():
    server = ThreadingHTTPServer(('0.0.0.0', PORT), Handler)
    with connect() as db:
        code = meta(db, 'code')
    print('\n' + '='*64, flush=True)
    print('  EKOLOGICKÝ DETEKTÍV — kvíz pre triedu', flush=True)
    print('='*64, flush=True)
    if CLOUD:
        print('  AUTORSKÝ PIN:    nastavený ako tajná premenná prostredia', flush=True)
    else:
        print(f'  AUTORSKÝ PIN:    {ADMIN_PIN}', flush=True)
    print(f'  KÓD MIESTNOSTI:  {code}', flush=True)
    if not CLOUD:
        print(f'  Na tomto PC:     http://localhost:{PORT}', flush=True)
        for ip in get_lan_addresses():
            print(f'  Pre spolužiakov: http://{ip}:{PORT}', flush=True)
        print('\n  Obe zariadenia musia byť na rovnakej Wi-Fi.', flush=True)
    else:
        print('  Online verzia: odkaz sa zobrazí v hostingu (HTTPS).', flush=True)
    print('  Kvíz spustíš v autorskom paneli. Ukončenie: Ctrl+C.', flush=True)
    print('='*64 + '\n', flush=True)
    if not CLOUD and os.environ.get('EKO_NO_BROWSER') != '1':
        threading.Timer(0.7, lambda: webbrowser.open(f'http://localhost:{PORT}/admin')).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nServer bol ukončený.')
    finally:
        server.server_close()


if __name__ == '__main__':
    run()
