# Nahrávání a stahování souborů

Načti tento modul, když uživatel může nahrát, importovat, stáhnout, sdílet nebo nechat aplikaci načíst soubor či URL. Kontrolu přizpůsob typu souborů a dopadu projektu.

## Obsah

1. Povolené typy a skutečný obsah
2. Velikost, počet a zpracování
3. Názvy, cesty a úložiště
4. Autorizace a sdílení
5. Bezpečné zobrazování a stahování
6. Malware, aktivní obsah a karanténa
7. Import z URL a archivy
8. Soukromí, retence a logy
9. Povinné testy
10. Oficiální zdroje

## 1. Povolené typy a skutečný obsah

Samotná přípona nestačí. Soubor `fotka.jpg` může obsahovat jiný formát.

Ověř více vrstev:

- allowlist skutečně potřebných přípon;
- serverem zjištěný MIME typ;
- signaturu/magic bytes nebo bezpečné parsování formátu;
- konzistenci mezi příponou, MIME a obsahem;
- bezpečné chování při neznámém nebo poškozeném souboru.

Nespoléhej pouze na `Content-Type` poslaný prohlížečem. Blocklist typu „zakázat `.exe`“ nestačí, protože existuje mnoho dalších aktivních formátů.

Zvlášť prověř:

- SVG, HTML a XML, které mohou obsahovat skripty nebo externí odkazy;
- PDF a kancelářské dokumenty s aktivním obsahem;
- obrázky zpracovávané knihovnami s historickými zranitelnostmi;
- CSV/Excel export a import kvůli formula injection;
- audio/video a metadata;
- zdrojové kódy, šablony, ZIP a další archivy.

## 2. Velikost, počet a zpracování

- Nastav maximální velikost jednoho souboru i celého požadavku.
- Omez počet souborů, denní kvótu a souběžné zpracování.
- Limit v prohlížeči zopakuj na serveru a případně v reverse proxy/storage.
- Při streamování nepřijímej celý neomezený soubor do paměti.
- Nastav timeout a ukonči nedokončený upload.
- Omez rozměry obrázku, délku videa, počet stránek nebo jiný formátový rozměr.
- Při převodu používej izolovaný proces s omezením CPU, paměti, času a disku.
- Zabraň decompression/zip bomb: kontroluj počet položek, vnoření a celkovou rozbalenou velikost.
- Nezpracovávej soubor automaticky neomezeným počtem retry.

U drahého AI/OCR/transcoding zpracování přidej uživatelskou kvótu a budget limit.

## 3. Názvy, cesty a úložiště

### Názvy

- Vygeneruj vlastní náhodný identifikátor nebo bezpečný serverový název.
- Původní název uchovej pouze jako metadata po normalizaci a délkovém limitu.
- Odstraň řídicí znaky, cesty, nebezpečné Unicode a přebytečné tečky.
- Nenech uživatele přepsat existující soubor stejným názvem.

### Cesty

- Nikdy nepřipojuj nedůvěryhodný název přímo k filesystem cestě.
- Po normalizaci ověř, že výsledná cesta zůstává uvnitř povoleného kořene.
- Zabraň `../`, absolutním cestám, symlinkům a změně bucket/folder prefixu.

### Úložiště

- Soukromé soubory ukládej jako soukromé ve výchozím stavu.
- Na vlastním serveru ukládej mimo spustitelný webroot nebo na oddělenou doménu bez cookies.
- Zakáž spuštění uploadovaného obsahu.
- Odděl veřejné marketingové soubory od uživatelských dokumentů.
- Použij šifrování a nejmenší oprávnění služby.
- Preview a test nepřipojuj k produkčnímu bucketu bez jasného důvodu.

## 4. Autorizace a sdílení

Autorizaci kontroluj při každé operaci:

- upload;
- seznam souborů;
- náhled;
- stažení;
- změna metadat;
- sdílení;
- smazání;
- generování signed URL.

Uživatel nesmí změnou ID nebo cesty získat cizí soubor. Ověř dva testovací účty.

### Signed URLs

- Vydávej je až po serverové autorizaci.
- Použij krátkou expiraci odpovídající účelu.
- Nevydávej URL pro cizí objekt.
- Nezapisuj ji do veřejného logu nebo analytiky.
- Po změně oprávnění počítej s tím, že již vydaná URL může platit do expirace.

### CSRF

U cookie-based uploadu a mazání ověř ochranu proti podvrženému požadavku z cizí stránky. CORS samotný nestačí.

## 5. Bezpečné zobrazování a stahování

- U nedůvěryhodného souboru preferuj `Content-Disposition: attachment` místo inline zobrazení.
- Nastav správný `Content-Type` a `X-Content-Type-Options: nosniff`.
- Aktivní obsah servíruj z oddělené origin bez session cookies a citlivého přístupu.
- Nepoužívej uživatelský název přímo v response headeru bez bezpečného kódování; hrozí header injection.
- HTML/SVG nevracej jako běžnou součást stejné aplikace bez sanitizace a silného důvodu.
- U náhledu dokumentu používej bezpečný renderer a izolaci.
- U CSV/Excel exportu neutralizuj buňky začínající `=`, `+`, `-` nebo `@`, pokud mohou pocházet od uživatele.
- Metadata obrázků a dokumentů mohou obsahovat polohu, jméno nebo interní informace; podle účelu je odstraň.

## 6. Malware, aktivní obsah a karanténa

Podle rizika projektu použij:

1. upload do neveřejné karantény;
2. validaci formátu a velikosti;
3. antivirovou nebo content-disarm kontrolu;
4. bezpečnou transformaci, například re-encoding obrázku;
5. teprve potom zpřístupnění.

Antivirus není stoprocentní důkaz bezpečnosti a nemá nahradit allowlist, izolaci a autorizaci.

U veřejných uploadů, firemních dokumentů, PDF, archivů a souborů sdílených dalším uživatelům zvaž odbornější kontrolu.

Pokud sken selže nebo není dostupný, nerozhoduj automaticky „povoleno“. Použij bezpečný fail-closed nebo karanténu podle funkce.

## 7. Import z URL a archivy

### Import z URL

Načítání souboru z uživatelem zadané URL je zároveň SSRF riziko.

- Povol pouze `https` a důvěryhodné domény nebo bezpečný allowlist.
- Po DNS překladu i po redirectu blokuj private, loopback, link-local a cloud metadata adresy.
- Omez porty, redirecty, timeout, velikost a typ odpovědi.
- Neposílej interní cookies nebo Authorization header na cizí host.
- Ověř konečný obsah stejným upload pipeline jako lokální soubor.

### Archivy

- Omez počet položek, vnoření a rozbalenou velikost.
- Zabraň Zip Slip: položka nesmí rozbalit soubor mimo cílovou složku.
- Ignoruj nebo bezpečně řeš symlinky, device files a absolutní cesty.
- Neprováděj automaticky skripty ani instalaci z rozbaleného archivu.
- Skenuj jednotlivé relevantní položky.

## 8. Soukromí, retence a logy

- Sbírej jen potřebné soubory a vysvětli účel.
- Urči retenční dobu a skutečné smazání z primárního úložiště i záloh podle pravidel projektu.
- Loguj upload ID, uživatele, velikost, typ, výsledek kontroly a akci; neloguj celý obsah, signed URL ani citlivý název bez potřeby.
- Omez přístup pracovníků a služeb k obsahu.
- Zkontroluj, zda poskytovatel používá data k trénování nebo dalším účelům, pokud se soubor posílá do AI/OCR služby.
- Zálohuj soubory odděleně od databázových metadat a testuj obnovu vazeb.
- U incidentu zachovej hash, čas, vlastníka a audit trail bez dalšího otevírání nebezpečného souboru.

## 9. Povinné testy

V bezpečném testovacím prostředí ověř:

1. Soubor s povolenou příponou a nesprávným obsahem je odmítnut.
2. Nadlimitní soubor a příliš mnoho souborů jsou odmítnuty před drahým zpracováním.
3. Název s `../`, absolutní cestou nebo řídicími znaky nezmění umístění ani header.
4. Účet A nemůže číst, mazat ani podepsat URL souboru B.
5. Soukromý soubor není dostupný bez autorizace.
6. Aktivní HTML/SVG se nespustí ve stejné origin s uživatelovou session.
7. Opakovaný upload nebo retry nevytvoří neomezený počet jobů a nákladů.
8. ZIP s traversal nebo nepřiměřeným rozbalením je bezpečně odmítnut.
9. Import URL nemůže načíst localhost, private network ani metadata endpoint.
10. Smazání a obnova souboru odpovídají deklarovanému postupu.

## 10. Oficiální zdroje

Ověř aktuální doporučení:

- OWASP File Upload Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html
- OWASP Unrestricted File Upload: https://owasp.org/www-community/vulnerabilities/Unrestricted_File_Upload
- OWASP SSRF Prevention Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html

Do reportu uveď povolené formáty, storage, veřejnost bucketu, limit, kontrolní pipeline a to, zda byl obsah skutečně testován nebo pouze zkontrolován v kódu.
