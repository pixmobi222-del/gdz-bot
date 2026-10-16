#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ГДЗ-бот — книги + уроки + админка + подписки. v12
"""

import json
import logging
import os
import re
import sys
import tempfile
import time
from datetime import datetime, date, timedelta
from pathlib import Path

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardRemove,
)

from nz_client import NZClient

# ================== НАСТРОЙКИ ==================
BOT_TOKEN = "8950494157:AAHBgR5AqWtKmQ2PkoJMGIj2Kb8bu_VFe14"
MAIN_ADMIN_ID = 8896785169
CREATOR = "@uxteg"

NZ_LOGIN = "gricay_oleksandr27"
NZ_PASSWORD = "999982hb"

BASE_DIR = Path(__file__).parent
BOOKS_DIR = BASE_DIR / "books"
USERS_FILE = BASE_DIR / "users.json"
ADMINS_FILE = BASE_DIR / "admins.json"
ALLOWED_FILE = BASE_DIR / "allowed.json"
LOG_FILE = BASE_DIR / "bot.log"
WGET = "/data/data/com.termux/files/usr/bin/wget"

MAX_DAYS = 3650

EMOJI_POOL = ["📘", "📗", "📙", "📕", "📔", "📒", "📓", "📖", "📚"]

SEP = "━━━━━━━━━━━━━━━━━━━━━"
SEP2 = "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
ARROW = "▸"
BULLET = "▫️"

C_R = "\033[0m"
C_B = "\033[1m"
C_D = "\033[2m"
C_RED = "\033[91m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_MAGENTA = "\033[95m"
C_CYAN = "\033[96m"
C_WHITE = "\033[97m"


class TermuxFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: C_D + C_WHITE,
        logging.INFO: C_CYAN,
        logging.WARNING: C_YELLOW,
        logging.ERROR: C_RED,
        logging.CRITICAL: C_B + C_RED,
    }
    ICONS = {
        logging.DEBUG: "🔍",
        logging.INFO: "✨",
        logging.WARNING: "⚠️ ",
        logging.ERROR: "❌",
        logging.CRITICAL: "🔥",
    }

    def format(self, record):
        color = self.COLORS.get(record.levelno, C_WHITE)
        icon = self.ICONS.get(record.levelno, "•")
        ts = datetime.now().strftime("%H:%M:%S")
        return f"{C_D}{ts}{C_R} {icon} {color}{record.getMessage()}{C_R}"


def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    for h in list(logger.handlers):
        logger.removeHandler(h)
    h_stdout = logging.StreamHandler(sys.stdout)
    h_stdout.setFormatter(TermuxFormatter())
    logger.addHandler(h_stdout)
    try:
        h_file = logging.FileHandler(LOG_FILE, encoding="utf-8")
        h_file.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S"
        ))
        logger.addHandler(h_file)
    except Exception:
        pass
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


setup_logging()
logger = logging.getLogger("gdz")

BOOKS_DIR.mkdir(exist_ok=True)


def banner():
    w = 56
    print()
    print(f"{C_CYAN}  ╔{'═' * w}╗{C_R}")
    print(f"{C_CYAN}  ║{C_R}   {C_B}{C_GREEN}⚡  G D Z   ·   B O T  ⚡{C_R}"
          f"{' ' * 29}{C_CYAN}║{C_R}")
    print(f"{C_CYAN}  ║{C_R}   {C_D}книги  ·  уроки  ·  ответы  ·  админка{C_R}"
          f"{' ' * 18}{C_CYAN}║{C_R}")
    print(f"{C_CYAN}  ╠{'═' * w}╣{C_R}")
    print(f"{C_CYAN}  ║{C_R}   {C_YELLOW}◆{C_R}  Создатель  {C_D}·{C_R}  "
          f"{C_B}{CREATOR}{C_R}{' ' * (28 - len(CREATOR))}{C_CYAN}║{C_R}")
    print(f"{C_CYAN}  ║{C_R}   {C_YELLOW}◆{C_R}  Платформа  {C_D}·{C_R}  "
          f"{C_B}Termux / Python{C_R}{' ' * 15}{C_CYAN}║{C_R}")
    print(f"{C_CYAN}  ╚{'═' * w}╝{C_R}")
    print()


def print_books_table(books: dict):
    if not books:
        print(f"  {C_YELLOW}⚠  Книг нет{C_R}\n")
        return
    print(f"  {C_B}{C_CYAN}📚  Загруженные книги{C_R}")
    print(f"  {C_D}{'─' * 64}{C_R}")
    for i, (bid, b) in enumerate(books.items(), 1):
        emoji = b.get("emoji", "📘")
        name = b.get("name", bid)
        mode = b.get("mode", "numbers")
        mode_icon = {"numbers": "🔢", "pages": "📄", "both": "🔀"}.get(mode, "🔢")
        total = len(b.get("numbers", {})) + len(b.get("pages", {}))
        name_short = name if len(name) <= 24 else name[:23] + "…"
        print(f"  {C_D}{i:>2}.{C_R} {emoji}  {C_B}{name_short:<26}{C_R}"
              f" {mode_icon}  {C_CYAN}{total:>4}{C_R} {C_D}материалов{C_R}")
    print(f"  {C_D}{'─' * 64}{C_R}")
    print(f"  {C_GREEN}✔{C_R}  Всего книг: {C_B}{len(books)}{C_R}\n")


# ================== ФАЙЛЫ ==================

JUNK_KEYS_RE = re.compile(
    r"^(Дослідження|Дослід|Перевірказнань|Перевірка|Повторення|Повтореннярозділу|"
    r"Підвищеноїскладності|Додатко|Додатков|Завданняпідвищеної|Самостійна|"
    r"Практична|Лабораторна|Екскурсія|Підсумкова|Контрольна|"
    r"Перевірказн|Тест|Запитання|Робочийзошит)\d*",
    re.IGNORECASE
)


def clean_book_data(data: dict) -> dict:
    for section in ("numbers", "pages"):
        section_data = data.get(section, {})
        if not isinstance(section_data, dict):
            continue
        cleaned = {}
        for k, v in section_data.items():
            if JUNK_KEYS_RE.match(str(k)):
                continue
            if re.fullmatch(r"\d+(\.\d+)?", str(k)):
                cleaned[k] = v
        data[section] = cleaned
    return data


def load_books():
    books = {}
    for f in BOOKS_DIR.glob("*.json"):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            data = clean_book_data(data)
            books[f.stem] = data
        except Exception as e:
            logger.warning(f"Не удалось прочитать {f}: {e}")
    return books


def save_book(book_id, book):
    path = BOOKS_DIR / f"{book_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(book, f, ensure_ascii=False, indent=2)


def load_users():
    if not USERS_FILE.exists():
        return {}
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def load_admins():
    if not ADMINS_FILE.exists():
        return []
    try:
        with open(ADMINS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data.get("ids", [])
            if isinstance(data, list):
                return data
            return []
    except Exception:
        return []


def save_admins(ids):
    with open(ADMINS_FILE, "w", encoding="utf-8") as f:
        json.dump({"ids": ids}, f, ensure_ascii=False, indent=2)


# ============ ДОСТУПЫ ============

def load_allowed():
    if not ALLOWED_FILE.exists():
        return {}
    try:
        with open(ALLOWED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # чистим главного из файла если он там
        if str(MAIN_ADMIN_ID) in data:
            del data[str(MAIN_ADMIN_ID)]
            save_allowed(data)
        # чистим записи не-админов, которые уже не юзеры — не нужно, оставляем
        return data
    except Exception:
        return {}


def save_allowed(data):
    with open(ALLOWED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def has_access(uid: int) -> bool:
    if uid == MAIN_ADMIN_ID:
        return True
    key = str(uid)
    if key not in ALLOWED:
        return False
    info = ALLOWED[key]
    until = info.get("until")
    if until is None:
        return True
    try:
        dt = datetime.fromisoformat(until)
        if dt < datetime.now():
            return False
        return True
    except Exception:
        return False


def access_status(uid: int) -> str:
    if uid == MAIN_ADMIN_ID:
        return "main"
    key = str(uid)
    if key not in ALLOWED:
        return "none"
    info = ALLOWED[key]
    until = info.get("until")
    if until is None:
        return "active"
    try:
        dt = datetime.fromisoformat(until)
        if dt < datetime.now():
            return "expired"
        return "active"
    except Exception:
        return "expired"


def user_display_name(uid: int) -> str:
    key = str(uid)
    u = USERS.get(key, {})
    name = u.get("first_name") or "—"
    uname = u.get("username")
    if uname:
        return f"{name} (@{uname})"
    return name


def give_access(uid: int, days: int = None) -> str:
    if uid == MAIN_ADMIN_ID:
        return "навсегда"
    if days is not None and days > MAX_DAYS:
        days = MAX_DAYS
    key = str(uid)
    info = ALLOWED.get(key, {})
    info["name"] = USERS.get(key, {}).get("first_name", info.get("name", ""))
    info["username"] = USERS.get(key, {}).get("username", info.get("username", ""))
    if days is None:
        info["until"] = None
        until_text = "навсегда"
    else:
        try:
            dt = datetime.now() + timedelta(days=days)
            info["until"] = dt.isoformat(timespec="seconds")
            until_text = f"до {dt.strftime('%d.%m.%Y')}"
        except OverflowError:
            info["until"] = None
            until_text = "навсегда"
    info["given_at"] = datetime.now().isoformat(timespec="seconds")
    info["status"] = "active"
    ALLOWED[key] = info
    save_allowed(ALLOWED)
    return until_text


def revoke_access(uid: int):
    if uid == MAIN_ADMIN_ID:
        return
    key = str(uid)
    if key in ALLOWED:
        ALLOWED[key]["status"] = "revoked"
        try:
            ALLOWED[key]["until"] = (datetime.now() - timedelta(seconds=1)).isoformat(timespec="seconds")
        except Exception:
            ALLOWED[key]["until"] = "2000-01-01T00:00:00"
        save_allowed(ALLOWED)


def access_until_str(uid: int) -> str:
    if uid == MAIN_ADMIN_ID:
        return "навсегда (главный)"
    key = str(uid)
    if key not in ALLOWED:
        return "нет"
    info = ALLOWED[key]
    until = info.get("until")
    if until is None:
        return "навсегда"
    try:
        dt = datetime.fromisoformat(until)
        return dt.strftime("%d.%m.%Y")
    except Exception:
        return "?"


BOOKS = load_books()
USERS = load_users()
ADMINS = load_admins()
ALLOWED = load_allowed()


def is_admin(uid: int) -> bool:
    return uid == MAIN_ADMIN_ID or uid in ADMINS


def next_free_emoji():
    used = {b.get("emoji") for b in BOOKS.values()}
    for e in EMOJI_POOL:
        if e not in used:
            return e
    return "📚"


bot = Bot(token=BOT_TOKEN, parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


# ================== ПАРСЕР HTML ==================

LINK_RE = re.compile(
    r'<a\s+href="(https://gdzonline\.net/uploads/book/[^"]+\.(?:jpg|jpeg|png))"[^>]*>([^<]+)</a>',
    re.IGNORECASE
)
TITLE_RE = re.compile(r"<title>([^<]+)</title>", re.IGNORECASE)
PAGE_FILE_RE = re.compile(r"[-_]page[-_]?(\d+)\.(?:jpg|jpeg|png)", re.IGNORECASE)


def parse_number(text: str):
    nums = []
    text = text.strip()

    if any(k in text for k in [
        "Самостійна", "Для перевірки", "Вправи для повторення",
        "Задачі підвищеної", "Для перевірки за курс",
        "Дослідження", "Перевірка знань", "Повторення",
    ]):
        return nums

    if re.search(r"(?:Стор[іи]нка|Стр\.?|С\.|Page|Р\.)\s*[№:]?\s*\d+",
                 text, re.IGNORECASE):
        return nums

    if "№" not in text and not re.match(r"^\d", text):
        return nums

    cleaned = text.replace("№", "").replace(" ", "")
    cleaned = re.sub(r"\([^)]*\)", "", cleaned)

    parts = cleaned.split("-")
    if len(parts) == 1:
        n = parts[0].strip(".")
        if n and re.fullmatch(r"\d+(\.\d+)?", n):
            nums.append(n)
        return nums

    left, right = parts[0].strip("."), parts[-1].strip(".")
    if not left or not right:
        return nums

    if "." in left and "." in right:
        try:
            a_major, a_minor = left.split(".", 1)
            b_major, b_minor = right.split(".", 1)
            if a_major == b_major:
                for i in range(int(a_minor), int(b_minor) + 1):
                    nums.append(f"{a_major}.{i}")
            else:
                nums.append(left); nums.append(right)
        except ValueError:
            nums.append(left); nums.append(right)
    else:
        try:
            for i in range(int(left), int(right) + 1):
                nums.append(str(i))
        except ValueError:
            nums.append(left); nums.append(right)
    return nums


def parse_page_from_text(text: str):
    text = text.strip()
    m = re.search(r"(?:Стор[іи]нка|Стр\.?|С\.|Page|Р\.)\s*[№:]?\s*(\d+)",
                  text, re.IGNORECASE)
    if m:
        return m.group(1).lstrip("0") or "0"
    if re.fullmatch(r"\d+", text):
        return text.lstrip("0") or "0"
    return None


def parse_html(raw: bytes):
    html = None
    for enc in ("utf-8", "cp1251", "latin-1"):
        try:
            html = raw.decode(enc, errors="ignore")
            break
        except Exception:
            continue
    if html is None:
        return {}, {}, "", "numbers"

    title = ""
    m = TITLE_RE.search(html)
    if m:
        title = m.group(1).strip()

    all_links = LINK_RE.findall(html)
    has_page_text = False
    for url, text in all_links:
        if re.search(r"(?:Стор[іи]нка|Стр\.?|С\.|Page|Р\.)\s*[№:]?\s*\d+",
                     text, re.IGNORECASE):
            has_page_text = True
            break

    numbers = {}
    pages = {}
    for url, text in all_links:
        page_from_text = parse_page_from_text(text)
        if page_from_text is not None:
            if page_from_text not in pages:
                pages[page_from_text] = url
            continue
        nums = parse_number(text)
        if nums:
            for n in nums:
                if n not in numbers:
                    numbers[n] = url
            continue
        text_stripped = text.strip()
        if has_page_text and re.fullmatch(r"\d+", text_stripped):
            page_num = text_stripped.lstrip("0") or "0"
            if page_num not in pages:
                pages[page_num] = url
            continue
        m_file = PAGE_FILE_RE.search(url)
        if m_file:
            page_num = m_file.group(1).lstrip("0") or "0"
            if page_num not in pages:
                pages[page_num] = url
            continue

    if has_page_text and pages and not numbers:
        auto_type = "pages"
    elif pages and not numbers:
        auto_type = "pages"
    elif numbers and not pages:
        auto_type = "numbers"
    elif numbers and pages:
        auto_type = "both"
    else:
        auto_type = "numbers"
    return numbers, pages, title, auto_type


def make_book_id(name: str):
    book_id = re.sub(r"[^a-z0-9]+", "_", name.lower())[:40].strip("_")
    if not book_id:
        book_id = f"book_{len(BOOKS) + 1}"
    if book_id in BOOKS:
        book_id = f"{book_id}_{len(BOOKS) + 1}"
    return book_id


def download_photo(url: str, out_path: str) -> bool:
    log_path = out_path + ".log"
    try:
        os.remove(out_path)
    except FileNotFoundError:
        pass
    cmd = (
        f'{WGET} -q -U "Mozilla/5.0 (Linux; Android 12)" '
        f'--referer="https://gdzonline.net/" '
        f'-O "{out_path}" "{url}" > "{log_path}" 2>&1'
    )
    os.system(cmd)
    if not os.path.exists(out_path):
        return False
    if os.path.getsize(out_path) < 1000:
        return False
    with open(out_path, "rb") as f:
        head = f.read(8)
    return head[:3] == b"\xff\xd8\xff" or head[:8] == b"\x89PNG\r\n\x1a\n"


# ================== ЮЗЕРЫ ==================

def get_user(uid: int, message: types.Message = None):
    key = str(uid)
    if key not in USERS:
        USERS[key] = {
            "id": uid, "username": "", "first_name": "",
            "requests": 0, "book": None,
            "last_number": None, "last_number_time": None,
            "first_seen": now_iso(), "last_seen": now_iso(),
            "total_seconds": 0, "session_start": time.time(),
        }
    if message:
        USERS[key]["username"] = message.from_user.username or USERS[key].get("username", "")
        USERS[key]["first_name"] = message.from_user.first_name or USERS[key].get("first_name", "")
        USERS[key]["last_seen"] = now_iso()
    save_users(USERS)
    return USERS[key]


def update_session_time(key: str):
    u = USERS.get(key)
    if not u:
        return
    start = u.get("session_start")
    if start:
        delta = time.time() - start
        if 0 < delta < 12 * 3600:
            u["total_seconds"] = u.get("total_seconds", 0) + int(delta)
    u["session_start"] = time.time()
    save_users(USERS)


def log_user(message: types.Message, action: str = ""):
    u = message.from_user
    name = u.first_name or u.username or str(u.id)
    uname = f"@{u.username}" if u.username else "—"
    logger.info(f"{C_MAGENTA}👤 {name}{C_R} {C_D}({uname}){C_R} → {C_YELLOW}{action}{C_R}")


def log_action(uid: int, action: str):
    name = user_display_name(uid)
    logger.info(f"{C_MAGENTA}👤 {name}{C_R} → {C_YELLOW}{action}{C_R}")


# ================== УРОКИ (NZ) ==================

SUBJECT_MAP = {
    "алгебра": ["algebra_9_ister"],
    "геометрія": ["geometry"],
    "українська мова": ["ukrmova"],
    "англійська мова": ["English_book", "English_workbook"],
    "хімія": ["himia"],
    "зарубіжна література": ["zarubizhna"],
    "українська література": ["ukr_literatura"],
}

UA_MONTHS = {
    "січня": 1, "лютого": 2, "березня": 3, "квітня": 4,
    "травня": 5, "червня": 6, "липня": 7, "серпня": 8,
    "вересня": 9, "жовтня": 10, "листопада": 11, "грудня": 12,
}

RU_WEEKDAYS = ["понедельник", "вторник", "среда", "четверг",
               "пятница", "суббота", "воскресенье"]
RU_MONTHS = ["", "января", "февраля", "марта", "апреля", "мая",
             "июня", "июля", "августа", "сентября", "октября",
             "ноября", "декабря"]


def normalize(s: str) -> str:
    return s.lower().replace("’", "'").replace("ʼ", "'").replace("`", "'").strip()


def find_books_by_subject(subject: str) -> list:
    s = normalize(subject)
    for key, ids in SUBJECT_MAP.items():
        if key in s:
            return [bid for bid in ids if bid in BOOKS]
    return []


def book_is_pages_mode(book_id: str) -> bool:
    book = BOOKS.get(book_id) or {}
    return book.get("mode") == "pages"


def book_is_both_mode(book_id: str) -> bool:
    book = BOOKS.get(book_id) or {}
    return book.get("mode", "numbers") == "both"


def book_is_zoshit(book_id: str) -> bool:
    book = BOOKS.get(book_id) or {}
    return "зошит" in normalize(book.get("name", ""))


def find_number_in_book(book_id: str, number: str):
    book = BOOKS.get(book_id)
    if not book:
        return None
    for n in (number, number.lstrip("0")):
        if n in book.get("numbers", {}):
            return book["numbers"][n]
        if n in book.get("pages", {}):
            return book["pages"][n]
    if "." in number and not number.endswith(".1"):
        sub = number + ".1"
        if sub in book.get("numbers", {}):
            return book["numbers"][sub]
        if sub in book.get("pages", {}):
            return book["pages"][sub]
    return None


# ============================================================
#           ПАРСЕР Д/З v9
# ============================================================

ORAL_KEYWORDS_RE = re.compile(
    r"\b(усно|устно|вивчити|вивч\.|читати|прочитати|опрацювати|"
    r"ознайомитись|ознайомитися|підготувати|підготуй|повторити|"
    r"повторіть|розповісти|розповідь|переказати|переказ|"
    r"пригадати|згадати|переглянути|відповісти|підготуватися)\b",
    re.IGNORECASE,
)


def split_hw_into_sentences(hw: str) -> list:
    if not hw:
        return []
    hw = hw.replace("\n", " ")
    protected = re.sub(r"(\d)\.(\d)", r"\1_\2", hw)
    parts = re.split(r"(?<=[.!?;])\s+(?=[А-ЯA-ZІЇЄҐ\d])", protected)
    result = []
    for p in parts:
        restored = p.replace("_", ".").strip(" \t,;.")
        if restored:
            result.append(restored)
    return result


def sentence_is_oral(sent: str) -> bool:
    if not sent:
        return False
    if re.search(r"\(\s*усно\s*\)|\(\s*устно\s*\)", sent, re.IGNORECASE):
        return True
    return bool(ORAL_KEYWORDS_RE.search(sent))


def sentence_is_topic(sent: str) -> bool:
    return bool(re.match(r"^\s*Тема\s*:", sent, re.IGNORECASE))


def sentence_is_date_only(sent: str) -> bool:
    s = sent.strip()
    if re.fullmatch(
        r"на\s+\d{1,2}\s+(?:січня|лютого|березня|квітня|травня|"
        r"червня|липня|серпня|вересня|жовтня|листопада|грудня)",
        s, re.IGNORECASE
    ):
        return True
    if re.fullmatch(r"на\s+\d{1,2}[\./]\d{1,2}", s):
        return True
    return False


def extract_written_numbers(hw: str) -> list:
    if not hw:
        return []

    seen_keys = set()
    results = []

    def _add(label, key):
        if key in seen_keys:
            return
        seen_keys.add(key)
        results.append((label, key))

    for sent in split_hw_into_sentences(hw):
        if sentence_is_topic(sent) or sentence_is_date_only(sent):
            continue

        for m in re.finditer(
            r"(\d+(?:\.\d+)?(?:\s*\([^)]*\))?)\s*\(\s*письм\w*\s*\)",
            sent, re.IGNORECASE,
        ):
            full = m.group(1).strip()
            km = re.match(r"(\d+(?:\.\d+)?)", full)
            if km:
                _add(full, km.group(1))

        for m in re.finditer(
            r"(?:вправ\w*|завданн\w*)\s*(\d+(?:\.\d+)?)(\s*\([^)]*\))?",
            sent, re.IGNORECASE,
        ):
            num = m.group(1)
            sub = m.group(2) or ""
            if re.search(r"\(\s*усно\s*\)|\(\s*устно\s*\)", sub, re.IGNORECASE):
                continue
            _add(f"вправа {num}{sub}", num)

        for m in re.finditer(r"[№#Nn][º°]?\s*", sent):
            tail = sent[m.end():]
            pos = 0
            pat = re.compile(r"(\d+(?:\.\d+)?)\s*(\([^)]*\))?")
            while pos < len(tail):
                mm = pat.match(tail, pos)
                if not mm:
                    break
                num = mm.group(1)
                sub = mm.group(2) or ""
                if re.search(r"\(\s*усно\s*\)|\(\s*устно\s*\)", sub, re.IGNORECASE):
                    pos = mm.end()
                    while pos < len(tail) and tail[pos] in " ,;":
                        pos += 1
                    continue
                _add(f"{num}{sub}", num)
                pos = mm.end()
                while pos < len(tail) and tail[pos] in " ,;":
                    pos += 1
                if pos < len(tail) and not tail[pos].isdigit():
                    break

        if not re.search(r"(?:вправ\w*|завданн\w*)\s*\d", sent, re.IGNORECASE) \
           and not re.search(r"[№#Nn][º°]?\s*\d", sent):
            for m in re.finditer(
                r"(?<![\d.])(\d+\.\d+)(\s*\([^)]*\))?(?![\d])",
                sent,
            ):
                num = m.group(1)
                sub = m.group(2) or ""
                if re.search(r"\(\s*усно\s*\)|\(\s*устно\s*\)", sub, re.IGNORECASE):
                    continue
                _add(f"{num}{sub}", num)

    return results


def extract_pages_from_hw(hw: str) -> list:
    if not hw:
        return []
    results = []

    simple_pats = [
        r"\bна\s+сторінці\s*(\d+)",
        r"\bсторінці\s*(\d+)",
        r"\bстор\.?\s*(\d+)",
        r"\bсторін\w*\s*(\d+)",
        r"\bс\.\s*(\d+)",
        r"\bpage\s*(\d+)",
    ]
    for pat in simple_pats:
        for mm in re.finditer(pat, hw, re.IGNORECASE):
            n = mm.group(1)
            if n not in results:
                results.append(n)

    range_pats = [
        r"\bс\.\s*(\d+)\s*[-–—]\s*\d+",
        r"\bстор\.?\s*(\d+)\s*[-–—]\s*\d+",
        r"\bсторін\w*\s*(\d+)\s*[-–—]\s*\d+",
        r"\bpage\s*(\d+)\s*[-–—]\s*\d+",
    ]
    for pat in range_pats:
        for mm in re.finditer(pat, hw, re.IGNORECASE):
            n = mm.group(1)
            if n not in results:
                results.append(n)

    return results


ZOSHIT_HINTS = ("друкованому зошит", "друкований зошит", "в зошит",
                "у зошит", "зошит", "workbook")
BOOK_HINTS = ("підручник", "в книз", "у книз", "в учебник", "учебник")


def pick_books_for_hw(subject: str, hw: str) -> list:
    all_ids = find_books_by_subject(subject)
    if not all_ids:
        return []
    hw_lower = normalize(hw)
    wants_zoshit = any(h in hw_lower for h in ZOSHIT_HINTS)
    wants_book = any(h in hw_lower for h in BOOK_HINTS)
    if wants_zoshit and not wants_book:
        filtered = [bid for bid in all_ids if book_is_zoshit(bid)]
        return filtered or all_ids
    if wants_book and not wants_zoshit:
        filtered = [bid for bid in all_ids if not book_is_zoshit(bid)]
        return filtered or all_ids
    return all_ids


def parse_day_date(title: str):
    m = re.search(r"(\d{1,2})\s+([а-яіїєґʼ']+)", title.lower())
    if not m:
        return None
    day = int(m.group(1))
    month = UA_MONTHS.get(m.group(2))
    if not month:
        return None
    today = date.today()
    year = today.year
    try:
        d = date(year, month, day)
    except ValueError:
        return None
    if (today - d).days > 30:
        try:
            d = date(year + 1, month, day)
        except ValueError:
            return None
    elif (d - today).days > 300:
        try:
            d = date(year - 1, month, day)
        except ValueError:
            return None
    return d


def fmt_day_title_ru(d: date) -> str:
    return f"{RU_WEEKDAYS[d.weekday()].capitalize()}, {d.day} {RU_MONTHS[d.month]}"


def fmt_day_button(d: date, today: date) -> str:
    if d == today:
        return f"🔥 Сегодня · {d.day:02d}.{d.month:02d}"
    if d == today + timedelta(days=1):
        return f"⚡ Завтра · {d.day:02d}.{d.month:02d}"
    return f"📅 {RU_WEEKDAYS[d.weekday()].capitalize()} · {d.day:02d}.{d.month:02d}"


_DAY_ITEMS_CACHE = {}


def _day_cache_key(day: dict) -> tuple:
    lessons_sig = tuple(
        (l.get("subject", ""), (l.get("hw") or "").strip())
        for l in day.get("lessons", [])
    )
    return (day.get("date"), lessons_sig)


def _clean_oral_sent(sent: str) -> str:
    if not sent:
        return ""
    clean = re.sub(r"\(\s*усно\s*\)|\(\s*устно\s*\)", "", sent, flags=re.IGNORECASE)
    clean = re.sub(r"\s+", " ", clean)
    clean = re.sub(r"\s*,\s*", ", ", clean)
    clean = re.sub(r",\s*(?=[,.;:]|$)", "", clean)
    clean = clean.strip(" ,;.")
    return clean


def _remove_written_from_text(text: str, written_keys: set, written_pages: set) -> str:
    if not text:
        return ""

    for key in sorted(written_keys, key=len, reverse=True):
        esc = re.escape(key)
        text = re.sub(
            rf"\bвправ\w*\s*{esc}\b(?:\s*\([^)]*\))?",
            "", text, flags=re.IGNORECASE
        )
        text = re.sub(
            rf"[№#Nn][º°]?\s*{esc}\b(?:\s*\([^)]*\))?",
            "", text, flags=re.IGNORECASE
        )

    for p in sorted(written_pages, key=len, reverse=True):
        esc = re.escape(p)
        text = re.sub(rf"\bна\s+сторінці\s*{esc}\b", "", text, flags=re.IGNORECASE)
        text = re.sub(rf"\bстор\.?\s*{esc}\b", "", text, flags=re.IGNORECASE)
        text = re.sub(rf"\bсторін\w*\s*{esc}\b", "", text, flags=re.IGNORECASE)
        text = re.sub(rf"\bс\.\s*{esc}\b", "", text, flags=re.IGNORECASE)

    text = re.sub(r"\(\s*письм\w*\s*\)|\(\s*пісьм\w*\s*\)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*,\s*", ", ", text)
    text = re.sub(r",\s*(?=[,.;:]|$)", "", text)
    text = re.sub(r"\s*;\s*", "; ", text)
    text = re.sub(r"\s*\.\s*", ". ", text)
    text = re.sub(r"\s+\.", ".", text)
    text = text.strip(" ,;.")
    return text


def collect_day_items(day: dict) -> tuple:
    cache_key = _day_cache_key(day)
    if cache_key in _DAY_ITEMS_CACHE:
        return _DAY_ITEMS_CACHE[cache_key]

    written = []
    oral = []

    for l in day.get("lessons", []):
        subject = l["subject"]
        hw_raw = (l.get("hw") or "").replace("\n", " ").strip()
        if not hw_raw:
            continue

        book_ids = pick_books_for_hw(subject, hw_raw)
        found_written = False
        written_keys = set()
        written_pages = set()

        if book_ids:
            nums = extract_written_numbers(hw_raw)
            for label, key in nums:
                for book_id in book_ids:
                    if find_number_in_book(book_id, key):
                        written.append({
                            "subject": subject,
                            "book_id": book_id,
                            "label": label,
                            "key": key,
                        })
                        written_keys.add(key)
                        found_written = True
                        break

            pages_to_check = extract_pages_from_hw(hw_raw)
            for book_id in book_ids:
                if not (book_is_pages_mode(book_id) or book_is_both_mode(book_id)):
                    continue
                for p in pages_to_check:
                    already = any(
                        w["book_id"] == book_id and w["key"] == p
                        for w in written
                    )
                    if already:
                        continue
                    if find_number_in_book(book_id, p):
                        written.append({
                            "subject": subject,
                            "book_id": book_id,
                            "label": f"с. {p}",
                            "key": p,
                        })
                        written_pages.add(p)
                        found_written = True

        oral_sents = []
        for sent in split_hw_into_sentences(hw_raw):
            if sentence_is_topic(sent) or sentence_is_date_only(sent):
                continue
            if not sentence_is_oral(sent):
                continue

            clean = _clean_oral_sent(sent)
            if not clean:
                continue

            clean = _remove_written_from_text(clean, written_keys, written_pages)
            if not clean:
                continue

            only_verbs = re.sub(
                r"\b(вивчити|вивч\.|виконати|виконайте|читати|прочитати|"
                r"опрацювати|ознайомитись|ознайомитися|підготувати|підготуй|"
                r"повторити|повторіть|розповісти|переказати|пригадати|"
                r"згадати|переглянути|відповісти|підготуватися)\b",
                "", clean, flags=re.IGNORECASE
            )
            if not only_verbs.strip(" ,;.:§"):
                if "§" not in clean:
                    continue

            oral_sents.append(clean)

        if oral_sents:
            oral_text = " ".join(oral_sents).strip()
            oral_text = re.sub(r"\s+", " ", oral_text)
            oral_text = re.sub(r"\s+\.\s*", ". ", oral_text)
            oral_text = re.sub(r"^[\s,;.]+|[\s,;]+$", "", oral_text)
            if oral_text and len(oral_text) > 2:
                if len(oral_text) > 260:
                    oral_text = oral_text[:260] + "…"
                oral.append({"subject": subject, "hw": oral_text})
        elif not found_written:
            short = hw_raw if len(hw_raw) <= 260 else hw_raw[:260] + "…"
            oral.append({"subject": subject, "hw": short})

    _DAY_ITEMS_CACHE[cache_key] = (written, oral)
    return written, oral


def build_days_menu(days: list) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    today = date.today()
    for d in days:
        parsed = parse_day_date(d["date"])
        if not parsed or parsed < today:
            continue
        w, o = collect_day_items(d)
        if not w and not o:
            continue
        kb.add(InlineKeyboardButton(
            fmt_day_button(parsed, today),
            callback_data=f"day:{parsed.isoformat()}"
        ))
    kb.add(InlineKeyboardButton("🔄 Обновить", callback_data="u:lessons_refresh"))
    kb.add(InlineKeyboardButton("🏠 В меню", callback_data="u:back"))
    return kb


SCHEDULE_CACHE = {"data": None, "ts": 0}
CACHE_TTL = 600


async def load_schedule(force: bool = False):
    global SCHEDULE_CACHE
    now = time.time()
    if not force and SCHEDULE_CACHE["data"] and (now - SCHEDULE_CACHE["ts"]) < CACHE_TTL:
        return SCHEDULE_CACHE["data"]
    try:
        async with NZClient(NZ_LOGIN, NZ_PASSWORD) as client:
            ok = await client.do_login()
            if not ok:
                logger.warning("NZ.UA: логин не удался")
                return None
            days = await client.get_diary_2weeks()
            SCHEDULE_CACHE["data"] = days
            SCHEDULE_CACHE["ts"] = now
            _DAY_ITEMS_CACHE.clear()
            return days
    except Exception as e:
        logger.error(f"Ошибка расписания: {e}")
        return None


async def send_day_lessons(message: types.Message, target_date: date):
    days = await load_schedule()
    if days is None:
        await message.answer(
            f"<b>⚠️ Ошибка загрузки</b>\n{SEP}\n"
            f"<i>Попробуй позже</i>"
        )
        return
    target_day = None
    for d in days:
        if parse_day_date(d["date"]) == target_date:
            target_day = d
            break
    if not target_day:
        await message.answer(
            f"<b>📅 {fmt_day_title_ru(target_date)}</b>\n{SEP}\n"
            f"<i>Уроков нет</i>"
        )
        return

    date_str = fmt_day_title_ru(target_date)
    written, oral = collect_day_items(target_day)

    if not written and not oral:
        await message.answer(
            f"<b>📅 Уроки на {date_str}</b>\n{SEP}\n\n"
            f"😔 <b>Нет данных</b>"
        )
        return

    await message.answer(
        f"<b>📅 Уроки на {date_str}</b>\n"
        f"{SEP}\n"
        f"✍️ Письменных: <b>{len(written)}</b>\n"
        f"💬 Устных: <b>{len(oral)}</b>"
    )

    if written:
        await message.answer(f"<b>✍️ Письменные задания</b>\n{SEP}")
        sent_urls = set()
        sent_count = 0
        for it in written:
            url = find_number_in_book(it["book_id"], it["key"])
            if not url or url in sent_urls:
                continue
            sent_urls.add(url)
            book = BOOKS.get(it["book_id"], {})
            book_name = book.get("name", it["book_id"])
            book_emoji = book.get("emoji", "📘")
            try:
                safe_key = it["key"].replace(".", "_")
                tmp_path = os.path.join(tempfile.gettempdir(),
                                        f"gdz_{it['book_id']}_{safe_key}.jpg")
                if not download_photo(url, tmp_path):
                    continue
                caption = (
                    f"{book_emoji} <b>{book_name}</b>\n"
                    f"{SEP2}\n"
                    f"📆 {date_str}\n"
                    f"📝 <b>{it['label']}</b>"
                )
                with open(tmp_path, "rb") as photo_file:
                    await message.answer_photo(photo=photo_file, caption=caption)
                sent_count += 1
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Ошибка фото {url}: {e}")
        if sent_count:
            await message.answer(f"✅ Отправлено: <b>{sent_count}</b> фото")

    if oral:
        text = f"<b>💬 Устные задания</b>\n{SEP}\n"
        for it in oral:
            text += f"\n{BULLET} <b>{it['subject']}</b>\n<i>{it['hw']}</i>\n"
        await message.answer(text)

    await message.answer(f"<b>🏁 Готово</b>\n{SEP}")


# ================== ЭКРАНЫ ДОСТУПА ==================

def access_denied_menu():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📩  Получить доступ", callback_data="req:access"))
    kb.add(InlineKeyboardButton(f"💬  Написать {CREATOR}",
                                url=f"https://t.me/{CREATOR.lstrip('@')}"))
    return kb


def access_expired_menu():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📩  Продлить подписку", callback_data="req:access"))
    kb.add(InlineKeyboardButton(f"💬  Написать {CREATOR}",
                                url=f"https://t.me/{CREATOR.lstrip('@')}"))
    return kb


async def show_access_denied(message: types.Message, expired: bool = False):
    if expired:
        text = (
            f"<b>⏰ Подписка закончилась</b>\n"
            f"{SEP}\n\n"
            f"Твоя подписка на бота истекла.\n"
            f"Это не блокировка — просто срок вышел.\n\n"
            f"Для продления напиши <b>{CREATOR}</b>\n"
            f"или нажми кнопку ниже\n\n"
            f"{SEP}\n"
            f"<i>После продления доступ снова откроется</i>"
        )
        await message.answer(text, reply_markup=access_expired_menu())
    else:
        text = (
            f"<b>🔒 Доступ закрыт</b>\n"
            f"{SEP}\n\n"
            f"📢 <b>Бот платный</b>\n\n"
            f"Для получения доступа напиши <b>{CREATOR}</b>\n"
            f"или нажми кнопку ниже — заявка придёт админу\n\n"
            f"{SEP}\n"
            f"<i>Обсуди условия с создателем</i>"
        )
        await message.answer(text, reply_markup=access_denied_menu())


# ================== МЕНЮ ==================

def user_main_menu():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📚  Книжки", callback_data="u:books"))
    kb.add(InlineKeyboardButton("📅  Уроки", callback_data="u:lessons"))
    kb.add(InlineKeyboardButton("📖  О боте", callback_data="u:about"))
    kb.add(InlineKeyboardButton("✍️  Связь с создателем", callback_data="u:contact"))
    return kb


def user_books_menu():
    kb = InlineKeyboardMarkup()
    for book_id, book in BOOKS.items():
        label = f"{book['emoji']}  {book['name']}"
        kb.add(InlineKeyboardButton(label, callback_data=f"book:{book_id}"))
    kb.add(InlineKeyboardButton("🏠  В меню", callback_data="u:back"))
    return kb


def admin_menu():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📚  Книги", callback_data="adm:books"))
    kb.add(InlineKeyboardButton("👥  Пользователи", callback_data="adm:users:0"))
    kb.add(InlineKeyboardButton("📊  Статистика", callback_data="adm:stats"))
    kb.add(InlineKeyboardButton("👑  Админы", callback_data="adm:admins"))
    return kb


def admin_books_menu():
    kb = InlineKeyboardMarkup()
    for book_id, book in BOOKS.items():
        label = f"{book['emoji']}  {book['name']}"
        kb.add(InlineKeyboardButton(label, callback_data=f"admb:{book_id}"))
    kb.add(InlineKeyboardButton("⬅️  Назад", callback_data="adm:back"))
    return kb


def admin_book_actions(book_id):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✏️  Сменить название", callback_data=f"admb:rename:{book_id}"))
    kb.add(InlineKeyboardButton("🎛  Режим поиска", callback_data=f"admb:mode:{book_id}"))
    kb.add(InlineKeyboardButton("🗑  Удалить книгу", callback_data=f"admb:delete:{book_id}"))
    kb.add(InlineKeyboardButton("⬅️  Назад", callback_data="adm:books"))
    return kb


def book_mode_menu(book_id):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔢  Только номера", callback_data=f"admm:numbers:{book_id}"))
    kb.add(InlineKeyboardButton("📄  Только страницы", callback_data=f"admm:pages:{book_id}"))
    kb.add(InlineKeyboardButton("🔀  Номера + страницы", callback_data=f"admm:both:{book_id}"))
    kb.add(InlineKeyboardButton("⬅️  Отмена", callback_data=f"admb:{book_id}"))
    return kb


def new_book_mode_menu():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🤖  Авто (рекомендуется)", callback_data="newmode:auto"))
    kb.add(InlineKeyboardButton("🔢  Только номера", callback_data="newmode:numbers"))
    kb.add(InlineKeyboardButton("📄  Только страницы", callback_data="newmode:pages"))
    kb.add(InlineKeyboardButton("🔀  Номера + страницы", callback_data="newmode:both"))
    return kb


def admin_users_menu(page: int):
    kb = InlineKeyboardMarkup()
    keys = [k for k in USERS.keys() if int(k) != MAIN_ADMIN_ID]
    per_page = 5
    start = page * per_page
    end = start + per_page
    for key in keys[start:end]:
        u = USERS[key]
        name = u.get("first_name") or u.get("username") or key
        uname = u.get("username")
        label = f"👤 {name} (@{uname})" if uname else f"👤 {name}"
        if len(label) > 55:
            label = label[:52] + "…"
        kb.add(InlineKeyboardButton(label, callback_data=f"admu:{key}"))
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"adm:users:{page-1}"))
    if end < len(keys):
        nav.append(InlineKeyboardButton("➡️", callback_data=f"adm:users:{page+1}"))
    if nav:
        kb.add(*nav)
    kb.add(InlineKeyboardButton("⬅️  Назад", callback_data="adm:back"))
    return kb


def admins_menu():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("➕  Добавить админа", callback_data="adm:addadmin"))
    for aid in ADMINS:
        kb.add(InlineKeyboardButton(f"➖  Убрать {aid}", callback_data=f"adm:deladmin:{aid}"))
    kb.add(InlineKeyboardButton("⬅️  Назад", callback_data="adm:back"))
    return kb


def request_admin_menu(uid: int):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ 1 день", callback_data=f"grant:1:{uid}"))
    kb.add(InlineKeyboardButton("✅ 7 дней", callback_data=f"grant:7:{uid}"))
    kb.add(InlineKeyboardButton("✅ 30 дней", callback_data=f"grant:30:{uid}"))
    kb.add(InlineKeyboardButton("✅ Навсегда", callback_data=f"grant:0:{uid}"))
    kb.add(InlineKeyboardButton("✏️ Свой срок", callback_data=f"grant:custom:{uid}"))
    kb.add(InlineKeyboardButton("❌ Отклонить", callback_data=f"grant:reject:{uid}"))
    return kb


# ================== FSM ==================

class AddBook(StatesGroup):
    waiting_file = State()
    waiting_mode = State()
    waiting_filename = State()
    waiting_name = State()
    waiting_emoji = State()


class RenameBook(StatesGroup):
    waiting_name = State()


class WriteUser(StatesGroup):
    waiting_text = State()


class AddAdmin(StatesGroup):
    waiting_id = State()


class CustomDays(StatesGroup):
    waiting_days = State()


# ================== ВСПОМОГАТЕЛЬНОЕ ==================

def mode_label(mode: str) -> str:
    return {
        "numbers": "🔢 Номера",
        "pages": "📄 Страницы",
        "both": "🔀 Номера + страницы",
    }.get(mode, "❓ Неизвестно")


def pick_auto_mode(numbers: dict, pages: dict) -> str:
    if numbers and not pages:
        return "numbers"
    if pages and not numbers:
        return "pages"
    if numbers and pages:
        return "both"
    return "numbers"


def filter_numbers(numbers: dict, mode: str) -> dict:
    return numbers if mode in ("numbers", "both") else {}


def filter_pages(pages: dict, mode: str) -> dict:
    return pages if mode in ("pages", "both") else {}


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def fmt_hours(seconds: float) -> str:
    hours = seconds / 3600
    if hours < 1:
        return f"{int(seconds / 60)} мин"
    return f"{hours:.1f} ч"


def user_card_text(uid: int) -> str:
    u = USERS.get(str(uid), {})
    name = u.get("first_name") or "—"
    uname = u.get("username") or "—"
    book_id = u.get("book")
    book_name = BOOKS.get(book_id, {}).get("name", "—") if book_id else "—"
    return (
        f"<b>👤 Пользователь</b>\n{SEP}\n\n"
        f"🆔 <code>{uid}</code>\n"
        f"👤 <b>{name}</b>\n"
        f"📎 @{uname}\n\n"
        f"📊 Запросов: <b>{u.get('requests', 0)}</b>\n"
        f"📚 Книга: {book_name}\n"
        f"🔢 Последний: <b>{u.get('last_number') or '—'}</b>\n"
        f"🕐 {u.get('last_number_time') or '—'}\n\n"
        f"⏱ В боте: <b>{fmt_hours(u.get('total_seconds', 0))}</b>\n"
        f"📅 Первый: {u.get('first_seen', '—')}\n"
        f"📅 Последний: {u.get('last_seen', '—')}\n\n"
        f"{SEP}\n"
        f"🔐 Доступ: <b>{access_until_str(uid)}</b>"
    )


def user_card_menu(uid: int):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✉️  Написать", callback_data=f"admw:{uid}"))
    if has_access(uid):
        kb.add(InlineKeyboardButton("🚫 Забрать доступ", callback_data=f"revoke:{uid}"))
    else:
        kb.add(InlineKeyboardButton("✅ Вернуть доступ", callback_data=f"grant:30:{uid}"))
    kb.add(InlineKeyboardButton("✏️ Изменить срок", callback_data=f"grant:custom:{uid}"))
    kb.add(InlineKeyboardButton("⬅️  Назад", callback_data="adm:users:0"))
    return kb


# ================== ХЕНДЛЕРЫ ==================

@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message, state: FSMContext):
    if await state.get_state():
        await state.finish()
    get_user(message.from_user.id, message)
    update_session_time(str(message.from_user.id))
    status = access_status(message.from_user.id)
    log_user(message, f"/start · доступ: {status}")

    if status in ("main", "active"):
        pass
    elif status == "expired":
        await show_access_denied(message, expired=True)
        return
    else:
        await show_access_denied(message, expired=False)
        return

    await message.answer("⏳", reply_markup=ReplyKeyboardRemove())
    name = message.from_user.first_name or "друг"
    text = (
        f"<b>👋 Привет, {name}!</b>\n"
        f"{SEP}\n\n"
        f"⚡ Я помогу найти <b>готовые домашние задания</b>\n"
        f"и покажу <b>расписание</b> с ответами.\n\n"
        f"📚 <b>Книг в базе:</b> {len(BOOKS)}\n"
        f"📅 <b>Уроки:</b> из NZ.UA\n\n"
        f"{SEP}\n"
        f"👇 <i>Выбери раздел</i>"
    )
    await message.answer(text, reply_markup=user_main_menu())


@dp.message_handler(commands=["help"])
async def help_cmd(message: types.Message, state: FSMContext):
    if await state.get_state():
        await state.finish()
    get_user(message.from_user.id, message)
    status = access_status(message.from_user.id)
    log_user(message, f"/help · доступ: {status}")
    if status == "expired":
        await show_access_denied(message, expired=True)
        return
    if status == "none":
        await show_access_denied(message, expired=False)
        return
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🏠  В меню", callback_data="u:back"))
    await message.answer(
        f"<b>🆘 Помощь</b>\n"
        f"{SEP}\n\n"
        f"<b>📚 Книжки</b>\n"
        f"🔹 Выбери книгу\n"
        f"🔹 Напиши номер задания\n"
        f"🔹 Получи фото решения\n\n"
        f"<b>📅 Уроки</b>\n"
        f"🔹 Выбери день\n"
        f"🔹 Бот пришлёт ответы\n"
        f"🔹 В конце — устные задания\n\n"
        f"{SEP}\n"
        f"<i>💡 Начни с /start</i>",
        reply_markup=kb
    )


@dp.message_handler(commands=["admin"])
async def admin_cmd(message: types.Message, state: FSMContext):
    if await state.get_state():
        await state.finish()
    log_user(message, f"/admin · доступ: {access_status(message.from_user.id)}")
    if not is_admin(message.from_user.id):
        await message.answer(f"<b>⛔ Нет доступа</b>")
        return
    total_users = len([k for k in USERS.keys() if int(k) != MAIN_ADMIN_ID])
    total_requests = sum(u.get("requests", 0) for u in USERS.values())
    text = (
        f"<b>🛠 Админ-панель</b>\n{SEP}\n\n"
        f"👥 Юзеров: <b>{total_users}</b>\n"
        f"📨 Запросов: <b>{total_requests}</b>\n"
        f"📚 Книг: <b>{len(BOOKS)}</b>\n\n"
        f"{SEP}\n"
        f"👇 <b>Выбери раздел:</b>"
    )
    await message.answer(text, reply_markup=admin_menu())


# ---- Запрос доступа ----

@dp.callback_query_handler(lambda c: c.data == "req:access")
async def request_access(call: types.CallbackQuery):
    uid = call.from_user.id
    if uid == MAIN_ADMIN_ID:
        await call.answer("✅ У тебя всегда доступ", show_alert=True)
        return
    get_user(uid, call.message)
    update_session_time(str(uid))
    if has_access(uid):
        await call.answer("✅ У тебя уже есть доступ", show_alert=True)
        return

    await call.answer("📩 Заявка отправлена", show_alert=True)
    log_action(uid, "запрос доступа")

    try:
        await call.message.edit_text(
            f"<b>📩 Заявка отправлена</b>\n"
            f"{SEP}\n\n"
            f"Ожидай ответа от <b>{CREATOR}</b>\n\n"
            f"{SEP}\n"
            f"<i>Обычно отвечает быстро</i>"
        )
    except Exception:
        pass

    name = call.from_user.first_name or "—"
    uname = f"@{call.from_user.username}" if call.from_user.username else "нет"
    text = (
        f"<b>📩 Запрос на доступ</b>\n"
        f"{SEP}\n\n"
        f"👤 <b>{name}</b>\n"
        f"📎 {uname}\n"
        f"🆔 <code>{uid}</code>\n\n"
        f"{SEP}\n"
        f"👇 <b>Выбери срок:</b>"
    )
    try:
        await bot.send_message(MAIN_ADMIN_ID, text, reply_markup=request_admin_menu(uid))
    except Exception as e:
        logger.error(f"Не могу отправить запрос админу: {e}")


# ---- Выдача доступа ----

@dp.callback_query_handler(lambda c: c.data.startswith("grant:"))
async def grant_access_cb(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Только админ", show_alert=True)
        return

    parts = call.data.split(":", 2)
    action = parts[1]
    target = parts[2] if len(parts) > 2 else None

    try:
        target_uid = int(target) if target else 0
    except ValueError:
        target_uid = 0

    if target_uid == MAIN_ADMIN_ID:
        await call.answer("❌ Главному нельзя менять доступ", show_alert=True)
        return
    if target_uid == call.from_user.id and call.from_user.id != MAIN_ADMIN_ID:
        # доп админ не может себе
        pass

    if action == "reject":
        uid = target_uid
        log_action(call.from_user.id, f"отклонил доступ {uid}")
        try:
            await bot.send_message(
                uid,
                f"<b>❌ Заявка отклонена</b>\n"
                f"{SEP}\n\n"
                f"Напиши {CREATOR} для уточнения"
            )
        except Exception:
            pass
        try:
            await call.message.edit_text(
                f"❌ Заявка от <code>{uid}</code> отклонена"
            )
        except Exception:
            pass
        await call.answer("Отклонено")
        return

    if action == "custom":
        uid = target_uid
        await state.update_data(target_uid=uid)
        await call.message.edit_text(
            f"<b>✏️ Свой срок</b>\n{SEP}\n\n"
            f"🆔 <code>{uid}</code>\n\n"
            f"Напиши число дней (макс <b>{MAX_DAYS}</b>)"
        )
        await CustomDays.waiting_days.set()
        await call.answer()
        return

    days = int(action)
    uid = target_uid
    until_text = give_access(uid, days if days > 0 else None)
    log_action(call.from_user.id, f"выдал доступ {uid} · {until_text}")

    try:
        await bot.send_message(
            uid,
            f"<b>✅ Доступ открыт</b>\n"
            f"{SEP}\n\n"
            f"Срок: <b>{until_text}</b>\n\n"
            f"{SEP}\n"
            f"<i>Напиши /start</i>"
        )
    except Exception:
        pass

    # обновим сообщение — покажем карточку юзера
    try:
        await call.message.edit_text(
            user_card_text(uid),
            reply_markup=user_card_menu(uid)
        )
    except Exception:
        pass
    await call.answer("✅ Выдано")


@dp.message_handler(state=CustomDays.waiting_days)
async def custom_days_save(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer("❌ Нужно число")
        return
    txt = message.text.strip()
    if not re.fullmatch(r"\d+", txt):
        await message.answer("❌ Только цифры")
        return
    days = int(txt)
    if days < 1:
        await message.answer("❌ Минимум 1 день")
        return
    if days > MAX_DAYS:
        await message.answer(
            f"❌ Максимум {MAX_DAYS} дней\n\nПопробуй снова или /cancel"
        )
        return
    data = await state.get_data()
    uid = data.get("target_uid")
    if not uid or uid == MAIN_ADMIN_ID:
        await state.finish()
        return
    until_text = give_access(uid, days)
    log_action(message.from_user.id, f"выдал доступ {uid} · {until_text}")
    try:
        await bot.send_message(
            uid,
            f"<b>✅ Доступ открыт</b>\n"
            f"{SEP}\n\n"
            f"Срок: <b>{until_text}</b>\n\n"
            f"{SEP}\n"
            f"<i>Напиши /start</i>"
        )
    except Exception:
        pass
    await message.answer(
        f"<b>✅ Доступ выдан</b>\n{SEP}\n\n"
        f"🆔 <code>{uid}</code>\n"
        f"Срок: <b>{days} дн</b>"
    )
    await state.finish()


@dp.callback_query_handler(lambda c: c.data.startswith("revoke:"))
async def revoke_access_cb(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔", show_alert=True)
        return
    uid = int(call.data.split(":", 1)[1])
    if uid == MAIN_ADMIN_ID:
        await call.answer("❌ Главному нельзя менять доступ", show_alert=True)
        return
    revoke_access(uid)
    log_action(call.from_user.id, f"забрал доступ {uid}")
    try:
        await bot.send_message(
            uid,
            f"<b>🚫 Доступ закрыт</b>\n"
            f"{SEP}\n\n"
            f"Напиши {CREATOR} для уточнения"
        )
    except Exception:
        pass
    await call.answer("🚫 Доступ забран")
    try:
        await call.message.edit_text(
            user_card_text(uid),
            reply_markup=user_card_menu(uid)
        )
    except Exception:
        pass


# ---- Меню ----

@dp.callback_query_handler(lambda c: c.data == "u:books")
async def u_books(call: types.CallbackQuery):
    uid = call.from_user.id
    if not has_access(uid):
        await call.answer("🔒 Нет доступа", show_alert=True)
        return
    get_user(uid, call.message)
    update_session_time(str(uid))
    log_action(uid, "меню книжки")
    if not BOOKS:
        await call.answer("Пока нет книг", show_alert=True)
        return
    text = (
        f"<b>📚 Книжки</b>\n"
        f"{SEP}\n"
        f"<i>Всего: {len(BOOKS)}</i>\n\n"
        f"👇 <b>Выбери книгу:</b>"
    )
    await call.message.edit_text(text, reply_markup=user_books_menu())
    await call.answer()


@dp.callback_query_handler(lambda c: c.data == "u:lessons")
async def u_lessons(call: types.CallbackQuery):
    uid = call.from_user.id
    if not has_access(uid):
        await call.answer("🔒 Нет доступа", show_alert=True)
        return
    log_action(uid, "меню уроки")
    await call.answer("⏳ Загружаю...")
    days = await load_schedule()
    if days is None:
        await call.message.edit_text(
            f"<b>⚠️ Ошибка</b>\n{SEP}\n"
            f"Не удалось загрузить\n"
            f"<i>Попробуй позже</i>"
        )
        return
    kb = build_days_menu(days)
    text = (
        f"<b>📅 На какой день показать уроки?</b>\n"
        f"{SEP}\n"
        f"<i>Показаны 2 недели</i>\n\n"
        f"👇 <b>Выбери день:</b>"
    )
    await call.message.edit_text(text, reply_markup=kb)


@dp.callback_query_handler(lambda c: c.data == "u:lessons_refresh")
async def u_lessons_refresh(call: types.CallbackQuery):
    uid = call.from_user.id
    if not has_access(uid):
        await call.answer("🔒 Нет доступа", show_alert=True)
        return
    log_action(uid, "обновление уроков")
    await call.answer("🔄 Обновляю...")
    days = await load_schedule(force=True)
    if days is None:
        await call.message.edit_text(
            f"<b>⚠️ Ошибка</b>\n{SEP}\n"
            f"Не удалось загрузить"
        )
        return
    kb = build_days_menu(days)
    text = (
        f"<b>📅 На какой день показать уроки?</b>\n"
        f"{SEP}\n"
        f"<i>🔄 Расписание обновлено</i>\n\n"
        f"👇 <b>Выбери день:</b>"
    )
    await call.message.edit_text(text, reply_markup=kb)


@dp.callback_query_handler(lambda c: c.data.startswith("day:"))
async def day_selected(call: types.CallbackQuery):
    uid = call.from_user.id
    if not has_access(uid):
        await call.answer("🔒 Нет доступа", show_alert=True)
        return
    iso = call.data.split(":", 1)[1]
    try:
        target = date.fromisoformat(iso)
    except ValueError:
        await call.answer("Ошибка даты", show_alert=True)
        return
    log_action(uid, f"день {iso}")
    await call.answer()
    try:
        await call.message.delete()
    except Exception:
        pass
    await send_day_lessons(call.message, target)


@dp.callback_query_handler(lambda c: c.data == "u:about")
async def u_about(call: types.CallbackQuery):
    uid = call.from_user.id
    if not has_access(uid):
        await call.answer("🔒 Нет доступа", show_alert=True)
        return
    log_action(uid, "о боте")
    total = sum(len(b.get("numbers", {})) + len(b.get("pages", {})) for b in BOOKS.values())
    text = (
        f"<b>📖 О боте</b>\n"
        f"{SEP}\n\n"
        f"🤖 <b>ГДЗ-бот</b>\n\n"
        f"📚 Книг: <b>{len(BOOKS)}</b>\n"
        f"🔢 Материалов: <b>{total}</b>\n"
        f"📅 Расписание: NZ.UA\n\n"
        f"{SEP}\n"
        f"👤 <b>Создатель:</b> {CREATOR}"
    )
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("⬅️  Назад", callback_data="u:back"))
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@dp.callback_query_handler(lambda c: c.data == "u:contact")
async def u_contact(call: types.CallbackQuery):
    uid = call.from_user.id
    log_action(uid, "контакт")
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("⬅️  Назад", callback_data="u:back"))
    await call.message.edit_text(
        f"<b>✍️ Связь с создателем</b>\n"
        f"{SEP}\n\n"
        f"💬 {CREATOR}\n\n"
        f"<i>Пиши по любым вопросам</i>",
        reply_markup=kb
    )
    await call.answer()


@dp.callback_query_handler(lambda c: c.data == "u:back")
async def u_back(call: types.CallbackQuery):
    uid = call.from_user.id
    if not has_access(uid):
        await call.answer("🔒 Нет доступа", show_alert=True)
        return
    log_action(uid, "в меню")
    get_user(uid, call.message)
    name = call.from_user.first_name or "друг"
    text = (
        f"<b>👋 Привет, {name}!</b>\n"
        f"{SEP}\n\n"
        f"⚡ Я помогу найти <b>готовые домашние задания</b>\n"
        f"и покажу <b>расписание</b> с ответами.\n\n"
        f"📚 <b>Книг в базе:</b> {len(BOOKS)}\n"
        f"📅 <b>Уроки:</b> из NZ.UA\n\n"
        f"{SEP}\n"
        f"👇 <i>Выбери раздел</i>"
    )
    await call.message.edit_text(text, reply_markup=user_main_menu())
    await call.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("book:"))
async def book_selected(call: types.CallbackQuery):
    uid = call.from_user.id
    if not has_access(uid):
        await call.answer("🔒 Нет доступа", show_alert=True)
        return
    book_id = call.data.split(":", 1)[1]
    book = BOOKS.get(book_id)
    if not book:
        await call.answer("Книга не найдена", show_alert=True)
        return
    get_user(uid, call.message)
    USERS[str(uid)]["book"] = book_id
    save_users(USERS)
    log_action(uid, f"книга {book['name']}")

    total = len(book.get("numbers", {})) + len(book.get("pages", {}))
    mode = book.get("mode", "numbers")
    mode_lbl = mode_label(mode)

    if mode == "both":
        hint = "💡 Напиши <code>ст 57 8</code> или <code>57</code>"
    elif mode == "pages":
        hint = "💡 Напиши номер страницы"
    else:
        hint = "💡 Напиши номер задания"

    text = (
        f"<b>✅ Книга выбрана</b>\n"
        f"{SEP}\n\n"
        f"{book['emoji']} <b>{book['name']}</b>\n\n"
        f"🎛 Режим: {mode_lbl}\n"
        f"📊 Материалов: <b>{total}</b>\n\n"
        f"{SEP}\n"
        f"{hint}"
    )
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📚  Другая книга", callback_data="u:books"))
    kb.add(InlineKeyboardButton("🏠  В меню", callback_data="u:back"))
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer("✅ Книга выбрана")


# ================== ВВОД ЧИСЕЛ ==================

NUMBER_ONLY_RE = re.compile(r"^\d+(\.\d+)?(\([^)]*\))?$")
PAGE_TASK_RE = re.compile(
    r"^(?:ст|стр|с|page|p)[\.\s]*(\d+)\s+(\d+(?:\.\d+)?(?:\([^)]*\))?)$",
    re.IGNORECASE
)


@dp.message_handler(lambda m: m.text and NUMBER_ONLY_RE.match(
    m.text.strip().replace("№", "").replace(" ", "")))
async def handle_number(message: types.Message):
    uid = message.from_user.id
    if not has_access(uid):
        await message.answer("🔒 Нет доступа. Напиши /start")
        return
    key = str(uid)
    raw = message.text.strip().replace("№", "").replace(" ", "")
    number = re.sub(r"\([^)]*\)", "", raw)

    u = get_user(uid, message)
    update_session_time(key)
    u["requests"] = u.get("requests", 0) + 1
    save_users(USERS)

    book_id = u.get("book")
    if not book_id or book_id not in BOOKS:
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📚  Выбрать книгу", callback_data="u:books"))
        await message.answer(
            f"<b>📚 Сначала выбери книгу!</b>\n{SEP}\n<i>Нажми кнопку ниже</i>",
            reply_markup=kb
        )
        return

    book = BOOKS[book_id]
    mode = book.get("mode", "numbers")

    url = None
    if mode in ("numbers", "both"):
        url = book.get("numbers", {}).get(number)
    if not url and mode in ("pages", "both"):
        url = book.get("pages", {}).get(number)
    if not url:
        url = book.get("numbers", {}).get(number) or book.get("pages", {}).get(number)
    if not url:
        url = find_number_in_book(book_id, number)

    if not url:
        log_user(message, f"число {number} — НЕ НАЙДЕНО")
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📚  Другая книга", callback_data="u:books"))
        kb.add(InlineKeyboardButton("🏠  В меню", callback_data="u:back"))
        await message.answer(
            f"<b>❌ Не найдено: {number}</b>\n{SEP}\n\n"
            f"{book['emoji']} <b>{book['name']}</b>\n\n"
            f"<i>💡 Проверь или попробуй <code>ст 57 8</code></i>",
            reply_markup=kb
        )
        return

    u["last_number"] = raw
    u["last_number_time"] = now_iso()
    save_users(USERS)
    log_user(message, f"число {raw} → {book['name']}")

    caption = (
        f"{book['emoji']} <b>{book['name']}</b>\n"
        f"{SEP2}\n"
        f"🔢 <b>{raw}</b>"
    )
    status = await message.answer("⏳ <i>Загружаю...</i>")
    try:
        safe = number.replace(".", "_")
        tmp_path = os.path.join(tempfile.gettempdir(), f"gdz_{safe}.jpg")
        if not download_photo(url, tmp_path):
            raise Exception("wget не скачал")
        try:
            await status.delete()
        except Exception:
            pass
        with open(tmp_path, "rb") as photo_file:
            await message.answer_photo(photo=photo_file, caption=caption)
        try:
            os.remove(tmp_path)
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Ошибка фото {url}: {e}")
        try:
            await status.delete()
        except Exception:
            pass
        await message.answer(
            f"<b>⚠️ Ошибка</b>\n{SEP}\n\n"
            f"{book['emoji']} <b>{book['name']}</b>\n"
            f"🔢 <b>{raw}</b>\n\n"
            f"🔗 <a href='{url}'>Открыть</a>"
        )


@dp.message_handler(lambda m: m.text and PAGE_TASK_RE.match(m.text.strip()))
async def handle_page_task(message: types.Message):
    uid = message.from_user.id
    if not has_access(uid):
        await message.answer("🔒 Нет доступа. Напиши /start")
        return
    key = str(uid)
    match = PAGE_TASK_RE.match(message.text.strip())
    page = match.group(1)
    task_raw = match.group(2)
    task = re.sub(r"\([^)]*\)", "", task_raw)

    u = get_user(uid, message)
    update_session_time(key)
    u["requests"] = u.get("requests", 0) + 1
    save_users(USERS)

    book_id = u.get("book")
    if not book_id or book_id not in BOOKS:
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📚  Выбрать книгу", callback_data="u:books"))
        await message.answer(
            f"<b>📚 Сначала выбери книгу!</b>\n{SEP}\n<i>Нажми кнопку ниже</i>",
            reply_markup=kb
        )
        return

    book = BOOKS[book_id]
    url = book.get("numbers", {}).get(task)
    label = f"№{task_raw}" if url else ""
    if not url:
        url = book.get("pages", {}).get(page)
        if url:
            label = f"с. {page}"
    if not url:
        url = find_number_in_book(book_id, task)
        if url:
            label = f"№{task_raw}"

    if not url:
        log_user(message, f"ст {page} {task_raw} — НЕ НАЙДЕНО")
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📚  Другая книга", callback_data="u:books"))
        kb.add(InlineKeyboardButton("🏠  В меню", callback_data="u:back"))
        await message.answer(
            f"<b>❌ Не найдено</b>\n{SEP}\n\n"
            f"{book['emoji']} <b>{book['name']}</b>\n"
            f"📄 стр. <b>{page}</b> · № <b>{task_raw}</b>\n\n"
            f"<i>💡 Проверь страницу и задание</i>",
            reply_markup=kb
        )
        return

    u["last_number"] = f"ст {page} {task_raw}"
    u["last_number_time"] = now_iso()
    save_users(USERS)
    log_user(message, f"ст {page} {task_raw} → {book['name']}")

    caption = (
        f"{book['emoji']} <b>{book['name']}</b>\n"
        f"{SEP2}\n"
        f"📄 стр. <b>{page}</b>\n"
        f"📝 <b>{label}</b>"
    )
    status = await message.answer("⏳ <i>Загружаю...</i>")
    try:
        tmp_path = os.path.join(tempfile.gettempdir(), f"gdz_{page}_{task}.jpg")
        if not download_photo(url, tmp_path):
            raise Exception("wget не скачал")
        try:
            await status.delete()
        except Exception:
            pass
        with open(tmp_path, "rb") as photo_file:
            await message.answer_photo(photo=photo_file, caption=caption)
        try:
            os.remove(tmp_path)
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Ошибка фото {url}: {e}")
        try:
            await status.delete()
        except Exception:
            pass
        await message.answer(
            f"<b>⚠️ Ошибка</b>\n{SEP}\n\n"
            f"{book['emoji']} <b>{book['name']}</b>\n"
            f"📄 стр. <b>{page}</b> · № <b>{task_raw}</b>\n\n"
            f"🔗 <a href='{url}'>Открыть</a>"
        )


# ================== АДМИН: ОБРАБОТЧИКИ ==================

@dp.callback_query_handler(lambda c: c.data == "adm:back")
async def adm_back(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    log_action(call.from_user.id, "админ-панель")
    total_users = len([k for k in USERS.keys() if int(k) != MAIN_ADMIN_ID])
    total_requests = sum(u.get("requests", 0) for u in USERS.values())
    text = (
        f"<b>🛠 Админ-панель</b>\n{SEP}\n\n"
        f"👥 Юзеров: <b>{total_users}</b>\n"
        f"📨 Запросов: <b>{total_requests}</b>\n"
        f"📚 Книг: <b>{len(BOOKS)}</b>\n\n"
        f"{SEP}\n"
        f"👇 <b>Выбери раздел:</b>"
    )
    await call.message.edit_text(text, reply_markup=admin_menu())
    await call.answer()


@dp.callback_query_handler(lambda c: c.data == "adm:books")
async def adm_books(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    if not BOOKS:
        await call.message.edit_text("📚 Книг нет.", reply_markup=admin_menu())
        await call.answer()
        return
    text = (
        f"<b>📚 Управление книгами</b>\n{SEP}\n"
        f"<i>Всего: {len(BOOKS)}</i>\n\n"
        f"👇 <b>Выбери книгу:</b>"
    )
    await call.message.edit_text(text, reply_markup=admin_books_menu())
    await call.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("admb:"))
async def adm_book_action(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    parts = call.data.split(":")
    action = parts[1]

    if action == "rename":
        book_id = parts[2]
        if book_id not in BOOKS:
            await call.answer("Книга не найдена", show_alert=True)
            return
        await state.update_data(rename_book_id=book_id)
        await call.message.answer(
            f"<b>✏️ Смена названия</b>\n{SEP}\n\n"
            f"Текущее:\n{BOOKS[book_id]['emoji']} <b>{BOOKS[book_id]['name']}</b>\n\n"
            f"{SEP}\n📝 <i>Пришли новое название</i>\n\n❌ /cancel — отмена"
        )
        await RenameBook.waiting_name.set()
        await call.answer()
        return

    if action == "mode":
        book_id = parts[2]
        if book_id not in BOOKS:
            await call.answer("Книга не найдена", show_alert=True)
            return
        current = BOOKS[book_id].get("mode", "numbers")
        await call.message.answer(
            f"<b>🎛 Режим поиска</b>\n{SEP}\n\n"
            f"📖 {BOOKS[book_id]['emoji']} <b>{BOOKS[book_id]['name']}</b>\n"
            f"Сейчас: {mode_label(current)}\n\n"
            f"{SEP}\n👇 <b>Выбери новый:</b>",
            reply_markup=book_mode_menu(book_id)
        )
        await call.answer()
        return

    if action == "delete":
        book_id = parts[2]
        if book_id not in BOOKS:
            await call.answer("Книга не найдена", show_alert=True)
            return
        book = BOOKS.pop(book_id)
        path = BOOKS_DIR / f"{book_id}.json"
        if path.exists():
            path.unlink()
        for k, info in USERS.items():
            if info.get("book") == book_id:
                info["book"] = None
        save_users(USERS)
        logger.warning(f"Книга удалена: {book['name']}")
        await call.message.edit_text(
            f"<b>🗑 Книга удалена</b>\n{SEP}\n\n"
            f"{book['emoji']} <b>{book['name']}</b>\n\n"
            f"📚 Осталось: <b>{len(BOOKS)}</b>",
            reply_markup=admin_books_menu()
        )
        await call.answer()
        return

    book_id = action
    if book_id not in BOOKS:
        await call.answer("Книга не найдена", show_alert=True)
        return
    book = BOOKS[book_id]
    mode = book.get("mode", "numbers")
    text = (
        f"{book['emoji']} <b>{book['name']}</b>\n{SEP}\n\n"
        f"🎛 Режим: {mode_label(mode)}\n"
        f"🔢 Номеров: <b>{len(book.get('numbers', {}))}</b>\n"
        f"📄 Страниц: <b>{len(book.get('pages', {}))}</b>\n"
        f"📁 ID: <code>{book_id}</code>\n\n{SEP}"
    )
    await call.message.edit_text(text, reply_markup=admin_book_actions(book_id))
    await call.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("admm:"))
async def adm_change_mode(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    parts = call.data.split(":")
    new_mode = parts[1]
    book_id = parts[2]
    if book_id not in BOOKS:
        await call.answer("Книга не найдена", show_alert=True)
        return
    BOOKS[book_id]["mode"] = new_mode
    save_book(book_id, BOOKS[book_id])
    book = BOOKS[book_id]
    text = (
        f"<b>✅ Режим изменён</b>\n{SEP}\n\n"
        f"{book['emoji']} <b>{book['name']}</b>\n\n"
        f"🎛 Режим: {mode_label(new_mode)}\n"
        f"🔢 Номеров: <b>{len(book.get('numbers', {}))}</b>\n"
        f"📄 Страниц: <b>{len(book.get('pages', {}))}</b>"
    )
    await call.message.edit_text(text, reply_markup=admin_book_actions(book_id))
    await call.answer("✅ Изменено")


# ================== АДМИН: ПОЛЬЗОВАТЕЛИ ==================

@dp.callback_query_handler(lambda c: c.data.startswith("adm:users:"))
async def adm_users(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    page = int(call.data.split(":")[2])
    keys = [k for k in USERS.keys() if int(k) != MAIN_ADMIN_ID]
    if not keys:
        await call.message.edit_text(
            "👥 Пользователей нет.",
            reply_markup=admin_menu()
        )
        await call.answer()
        return
    text = (
        f"<b>👥 Пользователи</b> · стр. {page+1}\n{SEP}\n"
        f"Всего: <b>{len(keys)}</b>\n\n"
        f"👇 <b>Выбери:</b>"
    )
    await call.message.edit_text(text, reply_markup=admin_users_menu(page))
    await call.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("admu:"))
async def adm_user_view(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    key = call.data.split(":", 1)[1]
    u = USERS.get(key)
    if not u:
        await call.answer("Не найден", show_alert=True)
        return
    uid = int(key)
    if uid == MAIN_ADMIN_ID:
        await call.answer("Это ты", show_alert=True)
        return
    await call.message.edit_text(
        user_card_text(uid),
        reply_markup=user_card_menu(uid)
    )
    await call.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("admw:"))
async def adm_write_to_user(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    key = call.data.split(":", 1)[1]
    if key not in USERS:
        await call.answer("Не найден", show_alert=True)
        return
    if int(key) == MAIN_ADMIN_ID:
        await call.answer("Это ты", show_alert=True)
        return
    await state.update_data(target_user=key)
    name = USERS[key].get("first_name") or "—"
    await call.message.answer(
        f"<b>✉️ Сообщение юзеру</b>\n{SEP}\n\n"
        f"👤 <b>{name}</b>\n"
        f"🆔 <code>{key}</code>\n\n"
        f"📝 <i>Напиши текст</i>\n\n❌ /cancel"
    )
    await WriteUser.waiting_text.set()
    await call.answer()


@dp.message_handler(state=WriteUser.waiting_text)
async def adm_write_send(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if not message.text or len(message.text.strip()) < 1:
        await message.answer("❌ Нужен текст. /cancel")
        return
    data = await state.get_data()
    key = data.get("target_user")
    if not key:
        await state.finish()
        return
    try:
        await bot.send_message(int(key), f"✉️ <b>Сообщение:</b>\n\n{message.text}")
        await message.answer("✅ Отправлено.")
        logger.info(f"Сообщение юзеру {key}: {message.text[:50]}")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    await state.finish()


@dp.callback_query_handler(lambda c: c.data == "adm:stats")
async def adm_stats(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    total_users = len([k for k in USERS.keys() if int(k) != MAIN_ADMIN_ID])
    total_requests = sum(u.get("requests", 0) for u in USERS.values())
    total_time = sum(u.get("total_seconds", 0) for u in USERS.values())
    total_books = len(BOOKS)
    total_materials = sum(
        len(b.get("numbers", {})) + len(b.get("pages", {}))
        for b in BOOKS.values()
    )
    text = (
        f"<b>📊 Статистика</b>\n{SEP}\n\n"
        f"👥 Юзеров: <b>{total_users}</b>\n"
        f"📨 Запросов: <b>{total_requests}</b>\n"
        f"⏱ Общее время: <b>{fmt_hours(total_time)}</b>\n\n"
        f"{SEP}\n\n"
        f"📚 Книг: <b>{total_books}</b>\n"
        f"🔢 Материалов: <b>{total_materials}</b>\n\n"
        f"{SEP}\n👑 Админов: <b>{len(ADMINS) + 1}</b>"
    )
    await call.message.edit_text(text, reply_markup=admin_menu())
    await call.answer()


# ================== АДМИНЫ ==================

@dp.callback_query_handler(lambda c: c.data == "adm:admins")
async def adm_admins(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Нет доступа", show_alert=True)
        return
    text = (
        f"<b>👑 Админы</b>\n{SEP}\n\n"
        f"👤 <b>Главный:</b>\n   <code>{MAIN_ADMIN_ID}</code>\n{SEP}\n"
    )
    if ADMINS:
        text += "\n👥 <b>Дополнительные:</b>\n"
        for aid in ADMINS:
            text += f"   • <code>{aid}</code>\n"
    else:
        text += "\n👥 <i>Дополнительных нет</i>\n"
    await call.message.edit_text(text, reply_markup=admins_menu())
    await call.answer()


@dp.callback_query_handler(lambda c: c.data == "adm:addadmin")
async def adm_addadmin_start(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Нет доступа", show_alert=True)
        return
    await call.message.answer(
        f"<b>👑 Добавить админа</b>\n{SEP}\n\n"
        f"📝 <i>Пришли ID юзера</i>\n\n"
        f"Например: <code>123456789</code>\n\n❌ /cancel"
    )
    await AddAdmin.waiting_id.set()
    await call.answer()


@dp.message_handler(state=AddAdmin.waiting_id)
async def adm_addadmin_save(message: types.Message, state: FSMContext):
    global ADMINS
    if not is_admin(message.from_user.id):
        return
    if not message.text:
        await message.answer("❌ Нужен ID. /cancel")
        return
    text = message.text.strip()
    if not re.fullmatch(r"\d+", text):
        await message.answer(
            f"<b>❌ Неверный формат</b>\n{SEP}\n\n"
            f"<i>ID должен быть числом</i>\n\n"
            f"Попробуй снова или /cancel"
        )
        return
    new_id = int(text)
    if new_id == MAIN_ADMIN_ID:
        await message.answer("❌ Это главный админ.")
        await state.finish()
        return
    if new_id in ADMINS:
        await message.answer("❌ Уже админ.")
        await state.finish()
        return
    ADMINS.append(new_id)
    save_admins(ADMINS)
    ADMINS = load_admins()
    logger.info(f"Админ добавлен: {new_id}")
    try:
        await bot.send_message(
            new_id,
            "👑 <b>Вам выдана админка</b>\n"
            f"{SEP}\n\n"
            "• /admin — панель\n"
            "• /addbook — добавить книгу\n"
            "• /logs — юзеры"
        )
    except Exception:
        pass
    await message.answer(
        f"<b>✅ Админ добавлен</b>\n{SEP}\n\n"
        f"🆔 <code>{new_id}</code>\n"
        f"👑 Всего: <b>{len(ADMINS) + 1}</b>"
    )
    await state.finish()


@dp.callback_query_handler(lambda c: c.data.startswith("adm:deladmin:"))
async def adm_deladmin(call: types.CallbackQuery):
    global ADMINS
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Нет доступа", show_alert=True)
        return
    aid = int(call.data.split(":")[2])
    if aid == MAIN_ADMIN_ID:
        await call.answer("Главного снять нельзя", show_alert=True)
        return
    if aid in ADMINS:
        ADMINS.remove(aid)
        save_admins(ADMINS)
        ADMINS = load_admins()
        logger.warning(f"Админ убран: {aid}")
        await call.answer(f"Удалён: {aid}")
    else:
        await call.answer("Не найден")
    text = (
        f"<b>👑 Админы</b>\n{SEP}\n\n"
        f"👤 <b>Главный:</b>\n   <code>{MAIN_ADMIN_ID}</code>\n{SEP}\n"
    )
    if ADMINS:
        text += "\n👥 <b>Дополнительные:</b>\n"
        for a in ADMINS:
            text += f"   • <code>{a}</code>\n"
    else:
        text += "\n👥 <i>Дополнительных нет</i>\n"
    await call.message.edit_text(text, reply_markup=admins_menu())


# ================== /addbook ==================

@dp.message_handler(commands=["addbook"])
async def addbook_start(message: types.Message, state: FSMContext):
    if await state.get_state():
        await state.finish()
    if not is_admin(message.from_user.id):
        log_user(message, "/addbook — отказ")
        await message.answer("⛔ Нет доступа.")
        return
    log_user(message, "/addbook")
    await message.answer(
        f"<b>📚 Добавление книги</b>\n{SEP}\n\n"
        f"<b>Шаг 1</b> {ARROW} <i>Пришли HTML-файл</i>\n"
        f"<i>с gdzonline.net</i>\n\n"
        f"{SEP}\n❌ /cancel — отмена"
    )
    await AddBook.waiting_file.set()


@dp.message_handler(state=AddBook.waiting_file, content_types=types.ContentTypes.DOCUMENT)
async def addbook_file(message: types.Message, state: FSMContext):
    doc = message.document
    fname = doc.file_name or "book.html"
    if not fname.lower().endswith((".html", ".htm")):
        await message.answer(
            f"<b>❌ Неверный формат</b>\n{SEP}\n\n"
            f"<i>Нужен .html или .htm</i>\n\n"
            f"📎 Пришли файл или /cancel"
        )
        return

    file = await bot.get_file(doc.file_id)
    raw = await bot.download_file(file.file_path)
    numbers, pages, title, auto_type = parse_html(raw.read())

    if not numbers and not pages:
        await message.answer("❌ Не удалось найти материалы. /cancel")
        return

    auto_mode = pick_auto_mode(numbers, pages)
    await state.update_data(numbers=numbers, pages=pages, fname=fname,
                            auto_title=title, auto_mode=auto_mode)
    logger.info(f"HTML разобран: {fname} — {len(numbers)} номеров, {len(pages)} страниц")

    hint = f"\n💡 Авто-название: <b>{title}</b>" if title else ""
    await message.answer(
        f"<b>✅ Файл разобран</b>\n{SEP}\n\n"
        f"🔢 Номеров: <b>{len(numbers)}</b>\n"
        f"📄 Страниц: <b>{len(pages)}</b>\n"
        f"🤖 Авто: {mode_label(auto_mode)}"
        f"{hint}\n\n"
        f"{SEP}\n👇 <b>Выбери режим:</b>",
        reply_markup=new_book_mode_menu()
    )
    await AddBook.waiting_mode.set()


@dp.message_handler(state=AddBook.waiting_file, content_types=types.ContentTypes.ANY)
async def addbook_wrong_content(message: types.Message, state: FSMContext):
    if message.text and message.text.startswith("/"):
        return
    await message.answer(
        f"<b>❌ Неверный формат</b>\n{SEP}\n\n"
        f"<i>Нужен HTML-файл</i>\n\n"
        f"📎 Пришли файл или /cancel"
    )


@dp.callback_query_handler(lambda c: c.data.startswith("newmode:"), state=AddBook.waiting_mode)
async def addbook_choose_mode(call: types.CallbackQuery, state: FSMContext):
    mode = call.data.split(":", 1)[1]
    data = await state.get_data()
    if mode == "auto":
        mode = data.get("auto_mode", "numbers")
    await state.update_data(chosen_mode=mode)

    auto_title = data.get("auto_title", "")
    hint = f"\n💡 Авто-название: <b>{auto_title}</b>" if auto_title else ""

    fname_hint = ""
    if auto_title:
        slug = re.sub(r"[^a-z0-9]+", "_", auto_title.lower())[:40].strip("_")
        if slug:
            fname_hint = f"\n\n💡 Например: <code>{slug}</code>"

    await call.message.edit_text(
        f"<b>🎛 Режим:</b> {mode_label(mode)}{hint}\n{SEP}\n\n"
        f"<b>Шаг 2</b> {ARROW} <i>Напиши имя файла</i>\n"
        f"<i>например</i> <code>fizyka</code>, <code>biologiya</code>"
        f"{fname_hint}\n\n"
        f"<i>Файл: books/имя.json</i>\n\n❌ /cancel"
    )
    await AddBook.waiting_filename.set()
    await call.answer()


@dp.message_handler(state=AddBook.waiting_mode, content_types=types.ContentTypes.ANY)
async def addbook_mode_wrong(message: types.Message, state: FSMContext):
    if message.text and message.text.startswith("/"):
        return
    await message.answer(
        f"<b>❌ Неверный ввод</b>\n{SEP}\n\n"
        f"<i>Выбери режим кнопкой выше</i>\n\n❌ /cancel"
    )


@dp.message_handler(state=AddBook.waiting_filename)
async def addbook_filename(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer(f"<b>❌ Нужен текст</b>\n{SEP}\n\n❌ /cancel")
        return

    raw = message.text.strip().lower()
    clean = re.sub(r"[^a-z0-9_\-]+", "_", raw).strip("_")

    if not clean or len(clean) < 2:
        await message.answer(
            f"<b>❌ Неверное имя</b>\n{SEP}\n\n"
            f"<i>Только латиница, цифры, _ и -</i>\n"
            f"<i>Минимум 2 символа</i>\n\n"
            f"Попробуй снова или /cancel"
        )
        return

    if clean in BOOKS:
        await message.answer(
            f"<b>⚠️ Такое имя уже есть</b>\n{SEP}\n\n"
            f"<code>{clean}.json</code> существует\n\n"
            f"📝 Другое имя или /cancel"
        )
        return

    path = BOOKS_DIR / f"{clean}.json"
    if path.exists():
        await message.answer(
            f"<b>⚠️ Файл существует</b>\n{SEP}\n\n"
            f"<code>{clean}.json</code> в папке\n\n"
            f"📝 Другое имя или /cancel"
        )
        return

    await state.update_data(book_id=clean)
    auto_title = (await state.get_data()).get("auto_title", "")
    hint = f"\n💡 Авто-название: <b>{auto_title}</b>" if auto_title else ""

    await message.answer(
        f"<b>📁 Имя файла:</b> <code>{clean}.json</code>{hint}\n{SEP}\n\n"
        f"<b>Шаг 3</b> {ARROW} <i>Напиши название книги</i>\n"
        f"<i>или</i> <code>авто</code>\n\n❌ /cancel"
    )
    await AddBook.waiting_name.set()


@dp.message_handler(state=AddBook.waiting_name)
async def addbook_name(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer(f"<b>❌ Нужен текст</b>\n{SEP}\n\n❌ /cancel")
        return

    data = await state.get_data()
    name = message.text.strip()

    if name.lower() == "авто":
        auto = data.get("auto_title", "")
        if not auto:
            await message.answer("❌ Авто пустое. Напиши вручную или /cancel.")
            return
        name = auto

    if not name or len(name) < 2:
        await message.answer(
            f"<b>❌ Неверный формат</b>\n{SEP}\n\n"
            f"<i>Не короче 2 символов</i>\n\n"
            f"Попробуй снова или /cancel"
        )
        return

    await state.update_data(name=name)
    await message.answer(
        f"<b>📖 Название:</b> {name}\n{SEP}\n\n"
        f"<b>Шаг 4</b> {ARROW} <i>Напиши эмодзи</i>\n"
        f"<i>или</i> <code>авто</code>\n\n❌ /cancel"
    )
    await AddBook.waiting_emoji.set()


@dp.message_handler(state=AddBook.waiting_emoji)
async def addbook_emoji(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer("❌ Нужен эмодзи. /cancel")
        return
    data = await state.get_data()
    emoji = message.text.strip()
    if emoji.lower() == "авто" or not emoji:
        emoji = next_free_emoji()
    if len(emoji) > 10:
        await message.answer(
            f"<b>❌ Неверный формат</b>\n{SEP}\n\n"
            f"<i>Слишком длинный текст</i>\n\n"
            f"Попробуй снова или /cancel"
        )
        return

    mode = data.get("chosen_mode", "numbers")
    numbers = filter_numbers(data["numbers"], mode)
    pages = filter_pages(data["pages"], mode)

    book_id = data.get("book_id")
    if not book_id:
        book_id = make_book_id(data["name"])

    book = {
        "name": data["name"],
        "emoji": emoji,
        "author": "—",
        "year": 2026,
        "url": "",
        "source_file": data.get("fname", ""),
        "mode": mode,
        "numbers": numbers,
        "pages": pages,
    }
    BOOKS[book_id] = book
    save_book(book_id, book)
    logger.info(f"Книга добавлена: {emoji} {data['name']} (ID: {book_id})")

    await message.answer(
        f"<b>✅ Книга добавлена</b>\n{SEP}\n\n"
        f"{emoji} <b>{data['name']}</b>\n\n"
        f"📁 Файл: <code>{book_id}.json</code>\n"
        f"🎛 Режим: {mode_label(mode)}\n"
        f"🔢 Номеров: <b>{len(numbers)}</b>\n"
        f"📄 Страниц: <b>{len(pages)}</b>\n\n"
        f"{SEP}\n📚 Всего: <b>{len(BOOKS)}</b>"
    )
    await state.finish()


@dp.message_handler(state=RenameBook.waiting_name)
async def rename_book_save(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    book_id = data.get("rename_book_id")
    if not book_id or book_id not in BOOKS:
        await message.answer("❌ Книга не найдена.")
        await state.finish()
        return
    new_name = message.text.strip() if message.text else ""
    if not new_name or len(new_name) < 2:
        await message.answer(
            f"<b>❌ Неверный формат</b>\n{SEP}\n\n"
            f"<i>Не короче 2 символов</i>\n\n"
            f"Попробуй снова или /cancel"
        )
        return
    old_name = BOOKS[book_id]["name"]
    BOOKS[book_id]["name"] = new_name
    save_book(book_id, BOOKS[book_id])
    logger.info(f"Книга переименована: {old_name} → {new_name}")
    await message.answer(
        f"<b>✅ Название изменено</b>\n{SEP}\n\n"
        f"Было: {old_name}\n"
        f"Стало: <b>{new_name}</b>"
    )
    await state.finish()


@dp.message_handler(commands=["cancel"], state="*")
async def cancel_cmd(message: types.Message, state: FSMContext):
    current = await state.get_state()
    if current:
        await state.finish()
        await message.answer(f"<b>✅ Отменено</b>\n{SEP}")
    else:
        await message.answer("Нечего отменять.")


# ================== /logs ==================

@dp.message_handler(commands=["logs"])
async def logs(message: types.Message, state: FSMContext):
    if await state.get_state():
        await state.finish()
    if not is_admin(message.from_user.id):
        log_user(message, "/logs — отказ")
        await message.answer("⛔ Нет доступа.")
        return
    log_user(message, "/logs")
    keys = [k for k in USERS.keys() if int(k) != MAIN_ADMIN_ID]
    if not keys:
        await message.answer("📊 Пользователей нет.")
        return
    lines = [f"<b>📊 Пользователи</b> ({len(keys)})\n"]
    for key in keys:
        u = USERS[key]
        uid = int(key)
        name = u.get("first_name") or "—"
        uname = u.get("username") or "—"
        book_id = u.get("book")
        book_name = BOOKS.get(book_id, {}).get("name", "—") if book_id else "—"
        lines.append(
            f"{SEP}\n"
            f"🆔 <code>{uid}</code>\n"
            f"👤 <b>{name}</b> · @{uname}\n"
            f"📨 Запросов: <b>{u.get('requests', 0)}</b>\n"
            f"📚 Книга: {book_name}\n"
            f"🔢 Последний: <b>{u.get('last_number') or '—'}</b>\n"
            f"⏱ В боте: <b>{fmt_hours(u.get('total_seconds', 0))}</b>\n"
            f"🔐 Доступ: <b>{access_until_str(uid)}</b>\n"
            f"📅 {u.get('last_seen', '—')}\n"
        )
    text = "\n".join(lines)
    if len(text) > 4000:
        parts = []
        cur = ""
        for line in lines:
            if len(cur) + len(line) > 3900:
                parts.append(cur)
                cur = line
            else:
                cur += line
        parts.append(cur)
        for part in parts:
            await message.answer(part)
    else:
        await message.answer(text)


# ================== ЗАПУСК ==================

if __name__ == "__main__":
    banner()
    print_books_table(BOOKS)
    print(f"  {C_D}👑 Главный админ:{C_R} {C_B}{MAIN_ADMIN_ID}{C_R}")
    if ADMINS:
        for a in ADMINS:
            print(f"     {C_D}•{C_R} {a}")
    else:
        print(f"     {C_D}(дополнительных нет){C_R}")
    print(f"  {C_D}📁 Файл доступов:{C_R} {C_B}{ALLOWED_FILE}{C_R}")
    print(f"  {C_D}📁 Файл логов:{C_R} {C_B}{LOG_FILE}{C_R}")
    print(f"\n  {C_GREEN}{C_B}🚀 Запуск бота...{C_R}\n")

    from aiogram import executor
    try:
        executor.start_polling(dp, skip_updates=True)
    except KeyboardInterrupt:
        print(f"\n  {C_YELLOW}⏹ Бот остановлен{C_R}")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        raise