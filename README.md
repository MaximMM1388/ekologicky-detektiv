# Ekologický detektív – ONLINE vydanie

Triedny interaktívny kvíz, ku ktorému sa spolužiaci pripájajú cez **HTTPS odkaz**, bez spoločnej Wi-Fi. Funguje na mobiloch. Šesť otázok, tímy alebo jednotlivci, autorský panel, percentá odpovedí, bodovanie a CSV export.

## Nasadenie online cez Render (bezplatný variant)

1. Na **GitHub** vytvor nové úložisko (repository), napríklad `ekologicky-detektiv`. Nahraj doň všetky súbory a priečinok `static` z tohto balíčka **do koreňového adresára**. Nenahrávaj náhodné lokálne databázy ani PIN.
2. Na **https://dashboard.render.com/** sa prihlás. Zvoľ **New → Blueprint** a pripoj svoj GitHub repozitár. Render prečíta súbor `render.yaml`.
3. Pri nastavovaní vyplň **EKO_ADMIN_PIN**: vlastných **8 až 12 číslic**. Je to tajné heslo do autorského panela – nedávaj ho spolužiakom, ani do GitHubu.
4. Potvrď vytvorenie služby na tarife **Free**. Po dokončení nasadenia Render poskytne adresu vo formáte `https://tvoj-nazov.onrender.com`. **To je odkaz pre spolužiakov.**
5. Otvor `https://tvoj-nazov.onrender.com/admin` a prihlás sa svojím PIN-om. Klikni **Spustiť kvíz**, potom **Kopírovať link**. Zdieľaj ho s triedou (na mobile sa vyplní kód miestnosti).
6. Sleduj priebežne štatistiky. Na konci stlač **Export CSV** a ulož si výsledky; až potom daj **Nová hra**.

**Ak pri vytváraní Blueprintu Render neponúkne Free:** založ namiesto toho `New → Web Service` z GitHub repozitára, vyber Python / Free, start command `python server.py`, build command `python --version` a v **Environment** nastav `EKO_CLOUD=1`, `EKO_ADMIN_PIN=<8–12 číslic>`.

## Dôležité obmedzenia bezplatného hostingu

- Render služby na Free sa po nečinnosti uspávajú, takže prvé otvorenie môže byť pomalšie. **Pred hodinou otvor stránku a skontroluj, že funguje.**
- Bezplatný Render nemá trvalý disk. **Pri reštarte, uspávaní či opätovnom nasadení sa môžu výsledky vymazať.** Exportuj si ich počas hodiny alebo hneď po skončení.
- Zadajte len **prezývky**, nie celé mená. Všetky odpovede vidí len autor s PIN-om. Použi PIN, ktorý nikto nepozná.
- Ak službu nepotrebuješ, môžeš ju po prezentácii z Render odstrániť.

## Lokálne testovanie

Na PC možno spustiť `python server.py` alebo Windows `spusti.bat` a otvoriť `http://localhost:8765`. Tento režim stále funguje bez internetu pre spolužiakov na rovnakej sieti. Na online test pred nasadením možno spustiť s environment premennými `EKO_CLOUD=1`, `EKO_ADMIN_PIN=12345678` a `PORT=8765`; testovací PIN potom zmeň pred verejným nasadením.

## Súbory

- `server.py` – backend, otázky, spracovanie odpovedí, výsledky, ochrana autorského panelu
- `static/index.html`, `styles.css`, `app.js` – používateľské rozhranie
- `render.yaml` – pripravená konfigurácia hostingu
- `.gitignore` – zabraňuje publikovaniu súkromných lokálnych dát

Poznámka: žiadne dáta sa neposielajú do externých analytických služieb; na hosťovanom webe ich však spracúva poskytovateľ hostingu.
