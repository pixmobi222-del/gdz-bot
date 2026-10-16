#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Клиент NZ.UA. Логин + получение щоденника + парсинг уроков.
2 недели: текущая + следующая.
"""

import asyncio
import re
from datetime import date, timedelta
from typing import Optional

import aiohttp
from bs4 import BeautifulSoup

NZ_BASE = "https://nz.ua"
NZ_LOGIN_URL = f"{NZ_BASE}/site/login"
NZ_DIARY_URL = f"{NZ_BASE}/schedule/diary"


class NZClient:
    def __init__(self, login: str, password: str):
        self.nz_login = login
        self.nz_password = password
        self.session: Optional[aiohttp.ClientSession] = None
        self.csrf_token: Optional[str] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers={
                "User-Agent": "Mozilla/5.0 (Linux; Android 12) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0.0.0 Mobile Safari/537.36",
            }
        )
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.session:
            await self.session.close()

    async def do_login(self) -> bool:
        async with self.session.get(NZ_LOGIN_URL) as resp:
            html = await resp.text()
            soup = BeautifulSoup(html, "html.parser")
            meta = soup.find("meta", {"name": "csrf-token"})
            if meta:
                self.csrf_token = meta.get("content")
            else:
                inp = soup.find("input", {"name": "_csrf"})
                if inp:
                    self.csrf_token = inp.get("value")

        if not self.csrf_token:
            return False

        data = {
            "_csrf": self.csrf_token,
            "LoginForm[login]": self.nz_login,
            "LoginForm[password]": self.nz_password,
            "LoginForm[rememberMe]": "1",
        }
        async with self.session.post(NZ_LOGIN_URL, data=data, allow_redirects=True) as resp:
            html = await resp.text()
            if 'name="LoginForm[login]"' in html or "login-form" in html:
                return False
            return True

    async def get_diary_week(self, start_date: Optional[str] = None) -> str:
        params = {"type": "for-school"}
        if start_date:
            params["start_date"] = start_date
        async with self.session.get(NZ_DIARY_URL, params=params) as resp:
            return await resp.text()

    async def get_diary_2weeks(self) -> list:
        today = date.today()
        monday_this = today - timedelta(days=today.weekday())
        monday_next = monday_this + timedelta(days=7)

        html1 = await self.get_diary_week(monday_this.isoformat())
        days1 = self.parse_diary(html1)

        html2 = await self.get_diary_week(monday_next.isoformat())
        days2 = self.parse_diary(html2)

        seen = set()
        result = []
        for d in days1 + days2:
            if d["date"] not in seen:
                seen.add(d["date"])
                result.append(d)
        return result

    @staticmethod
    def _extract_hw_from_box(box) -> str:
        """Ищет Д/з в разных возможных селекторах."""
        # Основной путь
        for row in box.select("div.diary-lesson-row"):
            text_el = row.select_one("div.diary-lesson-text")
            if not text_el:
                continue
            t = text_el.get_text("\n", strip=True)
            if t.startswith("Д/з:"):
                return t.replace("Д/з:", "").strip()
            # Fallback: ищем "Д/з" в любом месте
            if "Д/з" in t:
                idx = t.find("Д/з")
                return t[idx:].replace("Д/з:", "").replace("Д/з", "").strip(" :")
        # Дополнительно: любые span/div с "Д/з"
        for el in box.select("div, span, p"):
            t = el.get_text(" ", strip=True)
            if t.startswith("Д/з:"):
                return t.replace("Д/з:", "").strip()
        return ""

    @staticmethod
    def _extract_current_from_box(box) -> str:
        for row in box.select("div.diary-lesson-row"):
            text_el = row.select_one("div.diary-lesson-text")
            if not text_el:
                continue
            t = text_el.get_text("\n", strip=True)
            if t.startswith("Поточна:"):
                return t.replace("Поточна:", "").strip()
        return ""

    @staticmethod
    def parse_diary(html: str) -> list:
        soup = BeautifulSoup(html, "html.parser")
        days = []

        for item in soup.select("div.diary-item"):
            title_el = item.select_one("p.diary-item__title")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            title = re.sub(r"\s*—\s*(сьогодні|завтра|вчора)", "", title).strip()

            lessons = []
            for box in item.select("div.diary-box"):
                num_el = box.select_one("span.diary-item__num")
                time_el = box.select_one("span.diary-item__time")
                label_el = box.select_one("p.diary-item__label")
                cab_el = box.select_one("span.diary-item__cabinet")

                if not label_el:
                    continue

                num = num_el.get_text(strip=True).rstrip(".") if num_el else ""
                time_raw = time_el.get_text(" ", strip=True) if time_el else ""
                time_clean = re.sub(r"\s+", "-", time_raw)

                subject = label_el.get_text(strip=True)
                cabinet = cab_el.get_text(strip=True) if cab_el else ""

                current = NZClient._extract_current_from_box(box)
                hw = NZClient._extract_hw_from_box(box)

                lessons.append({
                    "num": num,
                    "time": time_clean,
                    "subject": subject,
                    "cabinet": cabinet,
                    "current": current,
                    "hw": hw,
                })

            days.append({"date": title, "lessons": lessons})

        return days


async def test():
    async with NZClient("gricay_oleksandr27", "999982hb") as client:
        ok = await client.do_login()
        print("Login:", ok)
        if not ok:
            return
        days = await client.get_diary_2weeks()
        for d in days:
            print(f"\n=== {d['date']} ===")
            for l in d["lessons"]:
                print(f"  {l['num']}. {l['time']} | {l['subject']}")
                if l["hw"]:
                    print(f"     Д/з: {l['hw'][:120]}...")


if __name__ == "__main__":
    asyncio.run(test())