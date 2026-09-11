# Základní bezpečnostní kontrola

Tento soubor načti při každém auditu. Použij jej jako rozhodovací mapu, ne jako mechanický seznam. Kontroluj pouze oblasti, které se projektu týkají, ale každou relevantní oblast uzavři stavem `OVĚŘENO`, `NÁLEZ`, `PODEZŘENÍ`, `NEOVĚŘENO` nebo `NETÝKÁ SE`.

## Obsah

1. Model hrozeb a hranice důvěry
2. Tajemství a klíče
3. Autentizace a hesla
4. Relace, cookies, CSRF a obnova účtu
5. Autorizace a oddělení uživatelů
6. Validace, injekce a práce s výstupem
7. Webhooky a integrace
8. Bezpečnost prohlížeče, hlavičky a CORS
9. Obchodní logika
10. Data, soukromí a cache
11. Debug, chyby a výjimečné stavy
12. Závislosti, runtime a dodavatelský řetězec
13. Logování, monitoring a reakce
14. Zálohy a obnova
15. Zneužití, dostupnost a nečekané náklady
16. Prostředí, doména a veřejná dostupnost
17. Povinné testy a důkazní standard
18. Oficiální zdroje

## 1. Model hrozeb a hranice důvěry

Nejdřív popiš, co se chrání a před kým. U každé citlivé funkce zakresli slovně cestu dat:

`zdroj vstupu -> validace -> autorizace -> zpracování -> uložení nebo akce -> výstup`

Za nedůvěryhodný vstup považuj zejména:

- URL parametry, query string, formuláře, JSON, headers, cookies a soubory;
- data z prohlížeče, i když je frontend vytvořil sám;
- webhooky a odpovědi externích API;
- obsah e-mailů, webů, dokumentů a databázových záznamů;
- text a strukturované výstupy AI modelu;
- názvy souborů, cesty, redirect URL a callback URL;
- hodnoty z GitHub issue, pull requestu, commitu nebo CI proměnné.

Urči chráněná aktiva:

- účty a relace;
- osobní a firemní data;
- platební stav, cena, licence a přístup k produktu;
- administrátorské operace;
- API klíče, doména, e-mailová reputace a cloudové náklady;
- dostupnost a možnost obnovy.

U víceuživatelského projektu určuj alespoň role: anonymní, přihlášený, vlastník záznamu, jiný uživatel, administrátor a systémová služba.

## 2. Tajemství a klíče

### Co ověřit

1. Rozlišuj lokální existenci `.env` souboru od jeho sledování gitem. Lokální `.env.local` může být správně; problém je commitnutá hodnota, historie, log, screenshot nebo klientský bundle.
2. Použij `git ls-files` nebo `scripts/safe_secret_scan.py`; nepoužívej prosté `find . -name '.env*'` jako důkaz úniku.
3. Zkontroluj všechny větve a historii, je-li to v rozsahu. Nález v historii považuj za možný únik, i když je současný soubor čistý.
4. Zkontroluj `.env.example`, ukázkové konfigurace, dokumentaci, testy, fixtures, CI workflow, Docker soubory a logy.
5. Zkontroluj, zda serverové tajemství není označeno klientským prefixem, například `NEXT_PUBLIC_`, `VITE_`, `REACT_APP_` nebo obdobou frameworku.
6. Je-li k dispozici build artefakt, zkontroluj také skutečný klientský JavaScript. Samotný název serverového souboru nezaručuje, že hodnota nebyla zabalena do prohlížeče.
7. Rozlišuj veřejné identifikátory od tajných hodnot. Například Stripe publishable key nebo Supabase publishable key mohou být veřejné; stále však nesmějí získat administrátorská oprávnění.
8. Zkontroluj scope, expiraci, prostředí a poslední použití klíče. Preferuj jeden omezený klíč pro jednu komponentu místo sdíleného univerzálního klíče.
9. Nikdy nevypisuj nalezenou hodnotu. Důkazem je typ, soubor, řádek, commit a bezpečně maskovaný konec.

### Když je nalezen skutečný klíč

Okamžitě načti `incident-response.md`. Pořadí je: omezit nebo zneplatnit -> nahradit v bezpečném úložišti -> znovu nasadit -> prověřit logy a zneužití -> až potom čistit historii.

## 3. Autentizace a hesla

Autentizace odpovídá na otázku „kdo to je“. Nezaměňuj ji s autorizací.

### Preferovaný přístup

- Preferuj prověřenou autentizační knihovnu nebo službu před vlastním řešením.
- Neimplementuj vlastní kryptografii, vlastní formát tokenu ani vlastní ukládání hesel bez silného důvodu a odborné revize.

### Hesla

- Neukládej ani neporovnávej hesla jako čitelný text.
- Použij funkci určenou pro hesla, typicky Argon2id, scrypt nebo přiměřeně nastavený bcrypt, podle doporučení používané platformy.
- Nepoužívej MD5, SHA-1 ani samotný SHA-256 pro ukládání hesel.
- `timingSafeEqual` není náhradou za password hashing. Používej ho jen tam, kde dává smysl pro porovnání stejně dlouhých tajných hodnot, podpisů nebo HMAC, a stále kontroluj okolní logiku.
- Zkontroluj bezpečnou změnu hesla, zneplatnění relací a ochranu proti změně e-mailu bez opětovného ověření.

### Přihlášení

- Omez opakované pokusy podle účtu, IP a rizika; neblokuj legitimní uživatele nekonečně.
- Chraň také registraci, obnovu hesla, jednorázové kódy, magic links a ověření e-mailu.
- Neprozrazuj zbytečně, zda konkrétní e-mail existuje. Odpověď a časování mají být přiměřeně jednotné.
- Administrátorské účty chraň vícefaktorovým přihlášením nebo passkey, pokud to služba podporuje.
- Zkontroluj výchozí účty a hesla, testovací uživatele a skryté bypassy.
- U OAuth/OIDC ověř přesnou redirect URL, `state`, případně nonce/PKCE podle flow, issuer a audience tokenu.

## 4. Relace, cookies, CSRF a obnova účtu

### Session cookies

Ověř podle architektury:

- `HttpOnly`, aby cookie nebyla běžně čitelná JavaScriptem;
- `Secure` v produkci;
- vhodné `SameSite`;
- úzký `Domain` a `Path`;
- rozumnou expiraci a idle timeout;
- rotaci identifikátoru relace po přihlášení nebo zvýšení oprávnění;
- skutečné zneplatnění při odhlášení, změně hesla a podezření na kompromitaci;
- žádný session token v URL, logu nebo analytice.

### CSRF

CSRF je podvržený změnový požadavek z cizí stránky, který využije uživatelovu přihlášenou cookie.

- U cookie-based autentizace ověř CSRF token nebo jinou odpovídající ochranu frameworku.
- `SameSite` používej jako vrstvu ochrany, ne jako univerzální náhradu všech CSRF kontrol.
- Změnové operace neprováděj přes `GET`.
- Ověř `Origin` nebo `Referer` tam, kde je to vhodné, zejména u citlivých endpointů.
- CORS není ochrana proti CSRF ani autorizace.

### Obnova účtu

- Token pro obnovu musí být náhodný, jednorázový, krátkodobý a bezpečně uložený.
- Po resetu zneplatni staré relace podle rizika.
- Odkaz nesmí prozrazit token do analytiky, refereru nebo třetích stran.
- Změna primárního e-mailu, 2FA nebo recovery metody má vyžadovat nové ověření a informovat uživatele.

## 5. Autorizace a oddělení uživatelů

Autorizace odpovídá na otázku „co tento konkrétní uživatel smí“.

### Povinné zásady

1. Ověřuj oprávnění na serveru u každého citlivého požadavku a každé citlivé operace.
2. Použij výchozí stav „zakázáno“, nikoli seznam několika známých zákazů.
3. Nevěř ID, roli, vlastníkovi, ceně ani stavu poslanému klientem.
4. Nezaměňuj přihlášení za oprávnění. Přihlášený uživatel nesmí automaticky vidět všechna data.
5. Nezaměňuj skryté tlačítko nebo redirect ve frontendu za serverovou ochranu.
6. Ověř horizontální přístup: účet A nesmí získat data účtu B změnou ID.
7. Ověř vertikální přístup: běžný uživatel nesmí volat administrátorskou funkci.
8. Ověř změnu chráněných polí: `owner_id`, `user_id`, `role`, `is_admin`, `price`, `paid`, `status`.
9. Ověř exporty, vyhledávání, agregace, notifikace, cache a realtime kanály; často unikají data mimo hlavní detail záznamu.
10. Ověř serverové jobs, webhooky a admin skripty. Zvýšený klíč musí být doplněn vlastní autorizací.

### Matice přístupů

Pro každou citlivou operaci vytvoř tabulku:

| Operace | Anonymní | Vlastník | Jiný uživatel | Administrátor | Systém |
|---|---|---|---|---|---|
| Číst | očekávání | očekávání | očekávání | očekávání | očekávání |
| Vytvořit | ... | ... | ... | ... | ... |
| Změnit | ... | ... | ... | ... | ... |
| Smazat | ... | ... | ... | ... | ... |

Je-li možné bezpečně testovat, použij dva testovací účty a reprodukovatelný test. U citlivých dat preferuj odpověď 404 nebo 403 podle záměru aplikace, ale hlavní je nevrátit data.

## 6. Validace, injekce a práce s výstupem

Validuj na serveru tvar, typ, délku, rozsah a povolené hodnoty. Frontendová validace je pouze pomoc pro uživatele.

### SQL a NoSQL

- Používej parametrizované dotazy nebo bezpečné API ORM.
- Neskládej strukturu dotazu z uživatelského textu.
- Omez dynamické názvy sloupců, řazení a filtry na allowlist.
- Ověř NoSQL operátory a dynamické objekty, které mohou změnit význam dotazu.

### Command injection

- Nedávej uživatelský vstup do shellového příkazu.
- Preferuj knihovní API a argumentové pole bez shellu.
- `shell=True`, `eval`, `exec`, dynamický `Function` a podobné konstrukce vyžadují silný důvod a ruční kontrolu.

### Path traversal

- Nepřipojuj uživatelský název přímo k cestě.
- Normalizuj cestu a ověř, že výsledný soubor zůstává v povoleném kořeni.
- Nepoužívej uživatelský název jako fyzický název uloženého souboru.

### SSRF

SSRF je situace, kdy aplikace načte uživatelem zadanou URL a útočník ji pošle k interní službě.

- Preferuj allowlist domén a protokolů.
- Blokuj loopback, private, link-local a cloud metadata adresy, včetně adres získaných až po DNS překladu nebo redirectu.
- Omez počet redirectů, velikost odpovědi, timeout a povolené porty.
- Nepřenášej interní cookies nebo autorizační hlavičky na cizí host.

### Open redirect

- Preferuj relativní interní cesty.
- Externí cíle povol jen z pevného allowlistu.
- Nenech přihlašovací nebo odhlašovací URL přesměrovat libovolně.

### XSS a HTML

- Spoléhej na bezpečné escapování frameworku.
- `innerHTML`, `dangerouslySetInnerHTML`, nebezpečné šablony a HTML z WYSIWYG editoru ručně zkontroluj.
- Sanitizuj podle cílového kontextu a použij udržovanou knihovnu.
- Výstup AI nebo Markdown rendereru považuj za nedůvěryhodný.
- Content Security Policy používej jako další vrstvu, ne jako náhradu správného escapování.

### Mass assignment a deserializace

- Nepředávej celý objekt požadavku přímo do databázového update.
- Vyber explicitně povolená pole.
- Nepoužívej nebezpečnou deserializaci nedůvěryhodných dat.
- U šablon a expression language nepouštěj uživatelský text jako výraz.

## 7. Webhooky a integrace

Pro každý příchozí webhook ověř:

- podpis nebo jiný autentizační mechanismus podle oficiálního SDK;
- podpis nad nezměněným raw body, pokud to služba vyžaduje;
- správný účet, prostředí a typ události;
- časové okno nebo ochranu proti replay, pokud je podporovaná;
- idempotenci: stejná událost nesmí být zpracována dvakrát se škodlivým efektem;
- nezávislost na pořadí událostí;
- autorizaci následné operace a vazbu na správného uživatele či objednávku;
- rychlou odpověď a bezpečnou frontu pro dlouhou práci;
- logování ID události bez tajných hodnot.

Odchozí integrace chraň omezenými klíči, timeoutem, retry limitem a redakcí logů.

## 8. Bezpečnost prohlížeče, hlavičky a CORS

Ověř skutečné hlavičky na nasazené URL, ne pouze konfigurační soubor.

### Doporučené oblasti

- `Content-Security-Policy`: posuď skutečnou sílu pravidel. Široké `*`, `unsafe-inline` nebo `unsafe-eval` mohou ochranu zásadně oslabit. Zaváděj opatrně a nejdřív lze použít report-only.
- `frame-ancestors` v CSP: určuj, kdo smí stránku vložit do iframe. `X-Frame-Options` může sloužit jako starší doplňková vrstva; nepoužívej automaticky `DENY`, pokud legitimní vložení potřebuješ.
- `X-Content-Type-Options: nosniff`.
- `Referrer-Policy` podle potřeby aplikace.
- `Strict-Transport-Security`: zapínej až po potvrzení, že celá zamýšlená doména a případné zahrnuté subdomény stabilně fungují přes HTTPS. `includeSubDomains` a preload nepřidávej bez rozmyslu.
- `Permissions-Policy` pro nepotřebné schopnosti prohlížeče.
- Bezpečné cache hlavičky u osobních a citlivých odpovědí.

### CORS

CORS určuje, zda JavaScript z jiné origin smí přečíst odpověď; není to vstupní firewall serveru.

- `Access-Control-Allow-Origin: *` může být správně u skutečně veřejného API bez credentials.
- U soukromého API s cookies nebo credentials použij přesný allowlist originů.
- Neodrážej libovolný příchozí `Origin` bez validace.
- Nepoužívej CORS jako náhradu autentizace a autorizace.
- Ověř preflight, povolené metody, headers a `Vary: Origin` u dynamického originu.

## 9. Obchodní logika

Automatický skener tuto oblast obvykle nepokryje. U každé hodnotné operace se ptej:

- Co může uživatel změnit, přeskočit nebo opakovat?
- Lze cenu, slevu, množství, roli, vlastníka nebo stav poslat z klienta?
- Lze použít slevový kód vícekrát, než je zamýšleno?
- Lze opakovaným kliknutím nebo retry vytvořit dvojí objednávku, platbu, e-mail nebo refundaci?
- Lze přeskočit ověření e-mailu, souhlas, platbu nebo schválení?
- Lze schválit vlastní žádost nebo kombinovat role, které mají být oddělené?
- Lze získat službu jen otevřením success URL?
- Lze změnou času, pořadí nebo souběžných požadavků obejít limit?
- Je kritická změna auditovaná a případně potvrzená druhým krokem?

U finančních a administrátorských operací zvaž transakci, idempotency key, unikátní databázové omezení a stavový automat.

## 10. Data, soukromí a cache

- Sbírej pouze data potřebná pro funkci.
- Odděl veřejná, interní, osobní a vysoce citlivá data.
- Ověř přístup při čtení, exportu, vyhledávání, záloze i mazání.
- Používej HTTPS a šifrování poskytovatele pro data v úložišti; klíčům a přístupům dej nejmenší oprávnění.
- Citlivá data nevkládej do URL, analytiky, chyb, logů, názvů souborů ani promptů bez důvodu.
- Ověř retenční dobu, mazání účtu a záloh podle povinností projektu.
- Osobní odpovědi nesmějí být omylem sdíleně cachované. Zkontroluj CDN, framework cache, statické generování a `Cache-Control`.
- Preview a testovací prostředí standardně nepoužívej s reálnými produkčními osobními údaji.
- U exportů přidej autorizaci, omezení rozsahu, audit a bezpečné doručení.

## 11. Debug, chyby a výjimečné stavy

- V produkci vypni debug režim a vývojářské toolbary.
- Veřejná chyba nesmí obsahovat stack trace, cesty, SQL, token, konfiguraci ani osobní data.
- Interní log má mít correlation/request ID, ale ne tajemství.
- Chybový stav nesmí automaticky přejít do povolujícího fallbacku, například „když ověření selže, pusť uživatele dál“.
- Ověř timeouty, částečné selhání, retry, dvojí odpověď, nedokončenou transakci a neočekávaný typ dat.
- Swagger, GraphQL introspection, phpMyAdmin, admin panely, health endpointy a debug rozhraní chraň podle záměru.
- Ověř, že `/.git`, zálohy, source maps, `.env`, logy a dočasné soubory nejsou veřejně dostupné.

## 12. Závislosti, runtime a dodavatelský řetězec

### Základ

- Urči skutečný package manager a používej odpovídající lockfile.
- Lockfile commitni a udržuj konzistentní; nesmí být více protichůdných lockfile bez vysvětlení.
- Ověř podporovanou verzi runtime a frameworku.
- Spusť audit přes `scripts/dependency_audit.py`; nic neinstaluj a nespouštěj automatický fix.
- Rozlišuj zranitelnost v dosažitelné produkční cestě od nepoužité vývojové závislosti, ale neignoruj ji bez důkazu.
- Aktualizaci hlavní verze testuj; nejnižší číslo CVE není důvod k bezhlavému rozbití aplikace.

### Další kontroly

- Ověř balíčky instalované přímo z Git URL, tarballu nebo neznámého registru.
- Prověř `preinstall`, `install`, `postinstall`, build hooks a neobvyklé skripty.
- Zkontroluj nově přidané balíčky, podobně vypadající názvy, opuštěné projekty a zbytečné závislosti.
- U CI/CD omez oprávnění tokenu, přístup k secrets a běh kódu z nedůvěryhodného forku.
- Externí CI actions nebo image připínej na důvěryhodnou neměnnou verzi tam, kde je dopad vysoký.
- Zkontroluj integrity a původ build artefaktu a kdo smí nasadit produkci.

## 13. Logování, monitoring a reakce

### Co logovat

- neúspěšná a riziková přihlášení;
- změny rolí, e-mailu, 2FA, klíčů a administrátorských nastavení;
- citlivé exporty, mazání a finanční operace;
- webhook ID a výsledek zpracování;
- chyby autorizace a neobvyklé objemy požadavků;
- deployment, změnu konfigurace a rotaci klíče.

### Co nelogovat

- hesla, celé tokeny, session cookies a privátní klíče;
- celé request bodies s osobními nebo finančními údaji bez nutnosti;
- raw Authorization header;
- system prompty nebo obsah dokumentů, pokud mohou obsahovat citlivá data.

### Alerting

Log bez upozornění nemusí pomoci včas. Ověř, kdo dostane zprávu při:

- prudkém nárůstu chyb, login pokusů nebo nákladů;
- opakovaném 401/403, neobvyklém admin přístupu nebo změně oprávnění;
- nedoručených webhoocích, selhání zálohy a výpadku;
- nalezení secretu nebo změně kritické konfigurace.

U každého alertu uveď vlastníka a očekávanou reakci.

## 14. Zálohy a obnova

Neověřuj pouze existenci tlačítka „backup“. Zjisti:

- co přesně se zálohuje: databáze, soubory, storage, konfigurace a secrets;
- frekvenci, retenci a oddělení od produkčního účtu;
- šifrování a přístup k zálohám;
- kdo smí obnovu provést;
- cílový čas obnovy a přijatelnou ztrátu dat;
- datum posledního skutečného testu obnovy;
- postup obnovy domény, DNS a posledního bezpečného deploymentu.

Záloha bez ověřené obnovy označ jako `NEOVĚŘENO`, ne jako vyřešenou ochranu.

## 15. Zneužití, dostupnost a nečekané náklady

U veřejného formuláře, AI endpointu, e-mailu, SMS, uploadu, vyhledávání a drahé úlohy kontroluj:

- rate limiting podle uživatele, IP, API klíče a celkového rozpočtu;
- maximální velikost požadavku, souboru, odpovědi a dávky;
- denní a měsíční kvóty;
- timeout, maximální počet retry a souběžných úloh;
- ochranu proti spamu a automatizaci;
- frontu s limitem a dead-letter postupem;
- budget alerts a tvrdé limity tam, kde je poskytovatel umožňuje;
- ochranu před nekonečnou rekurzí mezi webhooks, agenty nebo jobs;
- graceful degradation: drahá funkce se může vypnout bez pádu celé aplikace.

Samotný CAPTCHA widget nepovažuj za jedinou ochranu.

## 16. Prostředí, doména a veřejná dostupnost

### Oddělení prostředí

- Produkce, preview a vývoj mají vlastní klíče, databázi nebo bezpečně omezené datasety.
- Preview nepoužívá produkční administrátorský klíč.
- Testovací e-maily a SMS nejdou skutečným zákazníkům.
- Produkční secrets nejsou dostupné buildům z nedůvěryhodné větve nebo forku.
- Každé prostředí má jasné názvy a odpovídající callback/webhook URL.

### Veřejná dostupnost od každého deploymentu

Nespoléhej na to, že adresu nikdo nezná. Deployment URL může být veřejná, sdílená v PR, logu nebo historii a automaticky objevitelná. Každý veřejný deployment chraň ještě před zveřejněním odkazu.

- Zkontroluj `/admin`, `/debug`, API dokumentaci a testovací endpointy.
- Nepovažuj `robots.txt`, náhodnou URL nebo nepublikovanou doménu za autentizaci.
- Zkontroluj staré deploymenty a preview verze, ne pouze aktuální produkční doménu.

### Doména a DNS

- Účet registrátora a DNS poskytovatele má unikátní heslo, 2FA/passkey a bezpečnou obnovu.
- Doména má auto-renew, platnou platební metodu a registrar lock, je-li dostupný.
- Odstraň nevyužité DNS záznamy a dangling CNAME, které mohou umožnit převzetí subdomény.
- Záložní recovery e-mail nemá záviset jen na doméně, kterou chrání.
- DNSSEC a CAA doporuč podle podpory a provozního kontextu, ne mechanicky.

## 17. Povinné testy a důkazní standard

### Minimální důkaz

- `OVĚŘENO`: konkrétní konfigurace, test nebo odpověď nasazené aplikace.
- `NÁLEZ`: reprodukovatelný scénář nebo přímý důkaz s místem.
- `PODEZŘENÍ`: statický vzor bez dostatečného kontextu.
- `NEOVĚŘENO`: jasně popsaný chybějící přístup nebo nástroj.

### Povinné cílené testy podle funkce

- Přihlášení: neplatné údaje, rate limit, odhlášení, reset a zneplatnění relace.
- Autorizace: dva účty, cizí ID, přímý API požadavek a chráněná pole.
- Platby: změněná cena, opakovaný webhook, success URL bez ověřené platby.
- Upload: nesprávný typ, nadlimitní velikost, cizí soubor a bezpečné stažení.
- Webhook: chybějící/špatný podpis a opakované ID.
- AI: prompt injection z dokumentu, neoprávněný dokument, nebezpečný tool call a nákladový limit.
- Obnova: poslední doložený restore test.

Po opravě zopakuj stejný test, který nález odhalil. Nový kód bez testu není důkaz nápravy.

## 18. Oficiální zdroje

Před tvrzením závislým na verzi ověř aktuální oficiální dokumentaci. Výchozí zdroje:

- OWASP ASVS: https://owasp.org/www-project-application-security-verification-standard/
- OWASP Top 10: https://owasp.org/Top10/
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/
- OWASP GenAI Security Project: https://genai.owasp.org/

Nepřebírej slepě staré číslování, názvy dashboardů, ceny ani dostupnost funkcí. Do reportu uveď datum ověření zdroje.
