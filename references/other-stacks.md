# Další podporované stacky

Tento modul načti pro Django/Python, Laravel/PHP, Express/Node.js nebo jednoduché statické weby. Neodvozuj bezpečnost pouze z názvu frameworku. Nejdřív zjisti přesnou verzi, způsob nasazení, autentizaci, databázi a používané balíčky.

## Obsah

1. Společná pravidla
2. Django a Python
3. Laravel a PHP
4. Express a obecný Node.js server
5. Statické weby a frontend-only aplikace
6. Bezpečné ověřování

## 1. Společná pravidla

U každého stacku ověř:

- co běží v prohlížeči a co pouze na serveru;
- zda se tajemství nemohou dostat do klientského balíčku, logu nebo chybové stránky;
- zda autentizaci a autorizaci vynucuje server u každé citlivé operace;
- zda se vstupy validují na serveru a dotazy používají parametrizaci nebo bezpečné ORM;
- zda produkce nevypisuje stack trace, interní cesty, konfiguraci nebo celé požadavky;
- zda jsou oddělené vývojové, testovací a produkční klíče a databáze;
- zda se používá podporovaná verze runtime a frameworku;
- zda existuje lockfile nebo jiný reprodukovatelný záznam závislostí;
- zda je bezpečně nastavený reverse proxy, HTTPS, cookies, cache a práce s IP adresou klienta;
- zda byly zkontrolovány skutečné hlavičky a chování nasazené aplikace.

Příkaz frameworku nespouštěj jen proto, že vypadá diagnosticky. Může importovat a spustit projektový kód, připojit se k databázi nebo načíst produkční tajemství. Nejdřív vysvětli dopad a vyžádej si souhlas.

## 2. Django a Python

### Verze a konfigurace

Zjisti verzi Pythonu, Django a způsob správy balíčků. V produkční konfiguraci zkontroluj zejména:

- `DEBUG = False`;
- `SECRET_KEY` načítaný z bezpečné serverové proměnné, ne z repozitáře;
- konkrétní `ALLOWED_HOSTS`, nikoli bezdůvodné `*`;
- správné `CSRF_TRUSTED_ORIGINS`, bez širokých nebo cizích domén;
- `SECURE_SSL_REDIRECT` podle architektury a správně nastavený proxy header;
- `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_HTTPONLY` a přiměřený `SESSION_COOKIE_SAMESITE`;
- `CSRF_COOKIE_SECURE` a záměrné nastavení `CSRF_COOKIE_HTTPONLY`;
- HSTS až po ověření HTTPS na všech dotčených doménách;
- `SECURE_CONTENT_TYPE_NOSNIFF`, referrer policy a ochranu proti vložení do rámce;
- produkční e-mail, cache, storage a databázi oddělené od vývoje.

Nevyžaduj konkrétní hodnotu pouze proto, že ji Django nabízí. Posuď architekturu. Například aplikace vložená do legitimního iframe může potřebovat jinou politiku rámců než běžný web.

### Autentizace, oprávnění a administrace

Zkontroluj:

- zda projekt používá prověřený autentizační mechanismus místo vlastního ukládání hesel;
- zda jsou vlastní permission kontroly a object-level oprávnění použité u každého view, API endpointu a mutace;
- zda uživatel A nemůže změnou ID načíst či upravit objekt uživatele B;
- zda Django admin není veřejně použitelný s výchozím nebo slabým účtem;
- zda reset hesla neprozrazuje existenci účtu a token má omezenou platnost;
- zda citlivé účty používají vícefaktorové ověření, pokud to projekt podporuje;
- zda API framework, například Django REST Framework, nemá příliš široké výchozí permission classes.

### Databáze, formuláře a výstup

Zkontroluj:

- použití ORM nebo parametrizovaných dotazů; raw SQL skládané z textu uživatele je rizikové;
- formuláře a serializéry s explicitním seznamem povolených polí;
- aby uživatel nemohl poslat `is_staff`, `owner`, cenu, stav nebo jiné serverem řízené pole;
- bezpečné automatické escapování šablon a každé použití `safe`, `mark_safe` nebo neescapovaného HTML;
- serverovou validaci typů, délek, rozsahů a vlastnictví;
- transakce a ochranu před dvojím zpracováním citlivých operací.

### Soubory, statická média a úlohy

Zkontroluj:

- oddělení statických souborů od uživatelských uploadů;
- soukromé úložiště a autorizované stahování pro neveřejné soubory;
- limity uploadů, kontrolu skutečného formátu a bezpečné názvy;
- Celery, RQ, cron nebo management commands: autentizaci spouštěče, idempotenci, retry limity, logy a tajemství;
- že debug toolbar, API browser, Swagger/OpenAPI nebo interní diagnostika nejsou veřejné bez ochrany.

### Diagnostické příkazy

`python manage.py check --deploy` může být užitečný, ale importuje projekt a jeho nastavení. Spusť jej pouze po souhlasu, v bezpečném prostředí a bez produkčních mutací. Výsledek považuj za dílčí kontrolu, ne za kompletní audit.

Pro závislosti používej existující `pip-audit`, pokud je nainstalovaný a existuje vhodný lock nebo requirements soubor. Bodyguard nikdy nesmí `pip-audit` automaticky doinstalovat.

## 3. Laravel a PHP

### Verze a produkční konfigurace

Zjisti verzi PHP, Laravelu, Composeru a webového serveru. Zkontroluj zejména:

- `APP_ENV=production` a `APP_DEBUG=false` v nasazeném prostředí;
- `APP_KEY` jako tajnou, unikátní hodnotu mimo repozitář;
- správné `APP_URL`, HTTPS a trusted proxy nastavení;
- oddělené databáze, cache, queue, mail a storage mezi prostředími;
- bezpečné session cookies: `secure`, `http_only`, přiměřené `same_site`, doména a expirace;
- aby veřejný webroot ukazoval na adresář `public`, nikoli na kořen projektu;
- aby `.env`, `.git`, logy, zálohy, databázové dumpy a `storage` interní soubory nebyly dostupné přes web;
- aby produkční chyby neukazovaly stack trace, SQL, cesty ani hodnoty konfigurace.

Konfigurační cache může držet staré hodnoty. Přítomnost správného `.env` proto není důkaz, že nasazená aplikace používá správnou konfiguraci. Ověř živé chování a deployment postup.

### Hesla, autentizace a oprávnění

Zkontroluj:

- hesla přes `Hash::make()` / prověřený hasher, nikdy MD5, SHA-1 ani čitelný text;
- použití guards, policies, gates a middleware na serveru;
- object-level kontrolu vlastníka u modelů, souborů a administrace;
- aby skryté tlačítko ve Vue/React/Blade nebylo jedinou ochranou;
- rate limiting loginu, resetu hesla, jednorázových kódů a drahých endpointů;
- zneplatnění relace po odhlášení a citlivých změnách;
- bezpečné role a zákaz hromadného přiřazení administrátorských polí.

### CSRF, validace, ORM a šablony

Zkontroluj:

- CSRF ochranu u cookie-based mutací a zdůvodněné výjimky;
- Form Requests nebo ekvivalentní serverovou validaci;
- Eloquent/query builder s bindingem parametrů; raw dotazy a `whereRaw` s uživatelským textem ručně prověř;
- `$fillable`, `$guarded` a explicitní mapování polí proti mass assignment;
- Blade `{{ ... }}` pro escapovaný výstup; každé `{!! ... !!}` vyžaduje bezpečný původ nebo sanitizaci;
- bezpečné redirect cíle a validaci URL načítaných serverem;
- idempotenci plateb, webhooků, queue jobs a opakovaných formulářů.

### Soubory, fronty a plánované úlohy

Zkontroluj:

- Storage disky, jejich veřejnost a autorizaci stažení;
- limity uploadu, skutečný typ souboru, náhodné názvy a zákaz spuštění;
- queue dashboardy, Horizon, Telescope, Debugbar a log viewer proti veřejnému přístupu;
- retry limity a dead-letter postup u front;
- ochranu scheduler/cron endpointů a rotaci jejich tokenů;
- logy bez hesel, tokenů, cookies a úplných platebních či osobních údajů.

### Diagnostické příkazy

`php artisan route:list`, `about` nebo jiné Artisan příkazy bootují aplikaci a mohou spustit provider kód. Spusť je jen po souhlasu a ve vhodném prostředí. Nikdy automaticky nespouštěj migrace, seedy, queue workery ani cache-clearing příkazy.

Pro závislosti použij `composer audit --format=json --no-interaction`, pouze pokud existuje `composer.lock` a uživatelka souhlasí s online auditem.

## 4. Express a obecný Node.js server

Zkontroluj:

- podporovanou verzi Node.js a přesně zvolený package manager podle lockfilu;
- Helmet nebo ekvivalent, ale ověř skutečné hlavičky po nasazení;
- `trust proxy` pouze podle skutečné topologie; chybné nastavení může obejít limity nebo HTTPS detekci;
- session cookie, serverový session store a rotaci session ID po přihlášení;
- CSRF ochranu u cookie-based autentizace;
- CORS podle citlivosti API; wildcard není automatická chyba u veřejného neautentizovaného zdroje;
- limity těla požadavku, timeouty, rate limiting a ochranu drahých operací;
- centralizovaný error handler bez stack trace v produkci;
- parametrizované databázové dotazy a schema validaci na serveru;
- `child_process`, shell příkazy, práci s cestami, templating, `eval`, dynamické importy a serverové načítání URL;
- bezpečnou autorizaci každého routeru a objektu;
- WebSocket autentizaci, autorizaci zpráv, limity a odpojení po expiraci relace;
- graceful shutdown a chování při opakovaném doručení queue/webhook události.

Nepovažuj samotnou přítomnost balíčku `helmet`, `cors`, `express-rate-limit` nebo validační knihovny za důkaz, že je správně použitý.

## 5. Statické weby a frontend-only aplikace

Statický web má menší serverovou plochu, ale není automaticky bez rizika. Zkontroluj:

- zda build neobsahuje tajné klíče, neveřejné endpointy, source mapy s citlivým kódem nebo osobní data;
- zda všechny hodnoty dostupné frontendu mají pouze veřejná a omezená oprávnění;
- externí formuláře, analytiku, chat, newsletter a jejich zpracování osobních údajů;
- third-party skripty, jejich nutnost, původ, integritu a oprávnění;
- DOM XSS při práci s URL, query parametry, `innerHTML`, Markdownem a vloženým obsahem;
- bezpečnost hostingu, domény, DNS, HTTPS, cache a chybových stránek;
- zda „skrytá“ stránka nebo klientská kontrola hesla není vydávána za autentizaci;
- zda API volané z prohlížeče samo vynucuje autorizaci a limity.

Veřejný API klíč omezený na prohlížeč, doménu a úzké oprávnění může být záměrný. Nezaměňuj identifikátor určený pro klienta za serverové tajemství. Ověř rozsah a omezení u poskytovatele.

## 6. Bezpečné ověřování

U každého stacku preferuj tento sled:

1. Přečti manifesty, lockfily a konfiguraci bez spouštění projektu.
2. Najdi route, endpointy, permission vrstvy a datové modely.
3. Zkontroluj citlivé zdroje a datové toky.
4. Ověř nastavení služby nebo hostingu.
5. Proveď neškodnou kontrolu konkrétního deploymentu.
6. Teprve po souhlasu spusť frameworkový diagnostický příkaz, testy nebo build.
7. Po opravě zopakuj stejný test a ulož nový důkaz.

Když se doporučení liší podle verze frameworku, ověř aktuální oficiální dokumentaci. Při nejasnosti označ výsledek `NEOVĚŘENO`, nehádej.
