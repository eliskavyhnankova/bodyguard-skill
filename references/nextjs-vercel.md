# Next.js a Vercel

Načti tento modul, když projekt používá Next.js nebo Vercel. Nejdřív zjisti přesnou verzi Next.js a aktuální nastavení účtu; názvy funkcí a dostupnost podle tarifu ověř v oficiální dokumentaci v den auditu.

## Obsah

1. Rozpoznání verze a architektury
2. Autentizace a autorizace
3. Serverová a klientská hranice
4. Route Handlers, Server Actions a API
5. Cache a osobní data
6. Hlavičky a živé nasazení
7. Environment variables a prostředí
8. Deployment Protection a veřejné URL
9. Git integrace, build a zdrojový kód
10. Účty, provoz, náklady a obnova
11. Povinné testy
12. Oficiální zdroje

## 1. Rozpoznání verze a architektury

Zjisti:

- přesnou verzi `next` z `package.json` a lockfile;
- App Router (`app/`) nebo Pages Router (`pages/`), případně kombinaci;
- Route Handlers, API routes, Server Actions, Edge/Node runtime a middleware/proxy;
- autentizační knihovnu a místo přístupu k databázi;
- zda se používá Vercel, jiný hosting nebo vlastní server.

Od Next.js 16 je konvence `middleware.ts` přejmenovaná na `proxy.ts`. U staršího projektu hledej `middleware.ts`; u novějšího `proxy.ts`. Vždy však ověř aktuální dokumentaci a verzi projektu.

`proxy.ts` ani starší middleware nepovažuj za úplnou správu relace nebo jedinou autorizační vrstvu. Může dělat rychlé přesměrování, ale každá citlivá serverová operace musí autorizaci ověřit znovu u dat.

## 2. Autentizace a autorizace

### Zkontroluj

- Kde se načítá a ověřuje session: server, Route Handler, Server Action, data access layer.
- Zda chráněná stránka pouze přesměruje nepřihlášeného, nebo zda je chráněný i podkladový endpoint.
- Zda každá operace s konkrétním záznamem ověřuje vlastnictví nebo roli.
- Zda se role nebo `userId` neberou z formuláře, query nebo neověřeného JWT payloadu.
- Zda administrátorské cesty mají samostatnou serverovou kontrolu.
- Zda se session znovu ověřuje při citlivé Server Action, nikoli pouze při renderu stránky.
- Zda neexistuje fallback na prázdný, vývojový nebo hardcoded auth secret.

### Povinný test

Použij dva testovací účty. Zkopíruj request účtu A a nahraď ID záznamem účtu B. Server nesmí vrátit ani změnit cizí data.

## 3. Serverová a klientská hranice

### Klientské moduly

- Soubor s `'use client'` běží v prohlížeči. Nepoužívej v něm serverové klíče, databázové credentials ani zvýšeného Supabase/Stripe klienta.
- Klientské prefixy jako `NEXT_PUBLIC_` znamenají, že hodnota může skončit v browser bundle. Neumisťuj do nich secret, service-role, admin key, privátní klíč ani connection string.
- Nevěř tomu, že importovaný modul zůstane serverový pouze podle názvu. Zkontroluj skutečný import graph a build výstup.
- Používej mechanismus `server-only`, je-li vhodný, ale stále ověř build a architekturu.

### Server Components

- Server Component není automaticky autorizační hranice. Ověř oprávnění při přístupu k datům.
- Nepropouštěj secret nebo celý interní objekt přes props do Client Component.
- Serializovaný výstup do HTML nebo React payloadu může uživatel přečíst.

### Source maps a chybové výstupy

- Ověř, zda produkční source maps, stack traces nebo build logy neprozrazují interní cesty, zdrojový kód či hodnoty prostředí.
- Debug logy nesmějí tisknout `process.env`, request headers, cookies nebo celé session objekty.

## 4. Route Handlers, Server Actions a API

### Route Handlers a API routes

- Validuj metodu, Content-Type, velikost těla a vstupní schema.
- Ověř session a autorizaci uvnitř handleru.
- Nepoužívej CORS jako náhradu autorizace.
- Omez rate limit u loginu, formulářů, uploadů, AI a drahých operací.
- Nastav rozumný timeout a zacházej bezpečně s částečným selháním.
- U citlivých odpovědí ověř cache headers.

### Server Actions

- Považuj každou Server Action za veřejně volatelný serverový endpoint.
- Znovu ověř session, roli, vlastníka a všechna vstupní data.
- Neber `userId`, cenu, roli nebo stav jako autoritativní hodnotu z hidden inputu.
- Chraň opakované operace idempotencí nebo databázovým omezením.
- Ověř, že nepovolaná akce neuniká přes import do klienta nebo formulář jiné stránky.

### Redirects a callbacky

- Preferuj relativní interní cesty.
- `redirect`, `returnTo`, `callbackUrl` a podobné hodnoty validuj proti allowlistu.
- Ověř OAuth callbacky a preview/production domény odděleně.

## 5. Cache a osobní data

Next.js a Vercel mohou cachovat na více vrstvách. Ověř:

- zda odpověď závislá na session nebo uživateli není sdílená mezi uživateli;
- použití `use cache`, route cache, fetch cache, ISR, CDN a vlastní cache;
- zda cache key obsahuje bezpečný kontext, pokud je to opravdu nutné;
- zda po změně oprávnění nebo smazání dat nedochází k vracení starého obsahu;
- zda citlivé API odpovědi mají vhodné `Cache-Control`, typicky zákaz sdílené cache;
- zda preview nebo statický export neobsahuje produkční data.

U verze Next.js s Cache Components ověř aktuální pravidla přímo v dokumentaci dané verze; nespoléhej na staré chování frameworku.

## 6. Hlavičky a živé nasazení

Zkontroluj konfiguraci v `next.config.*`, `vercel.json`, Route Handleru nebo proxy, ale rozhoduj podle skutečné odpovědi nasazené URL.

Ověř:

- HTTPS a přesměrování z HTTP;
- Content Security Policy a její skutečnou sílu;
- `frame-ancestors`, případně doplňkový `X-Frame-Options`;
- `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`;
- HSTS až po potvrzení celé zamýšlené domény a subdomén;
- cookie flags bez zobrazení hodnoty;
- cache osobních odpovědí;
- CORS podle veřejnosti API a credentials;
- chybové stránky bez stack trace a interních údajů.

Samotná funkce `headers()` v kódu není důkaz. Hosting, route nebo CDN může hlavičku změnit.

## 7. Environment variables a prostředí

### Scope proměnných

V dashboardu ověř, pro která prostředí proměnná platí. Produkce, preview a development nemají automaticky sdílet stejné hodnoty.

### Povinné kontroly

- Preview nepoužívá produkční databázi ani produkční administrátorský klíč.
- Produkční secrets nejsou dostupné nedůvěryhodným větvím nebo forkům.
- Testovací a live Stripe, e-mail, AI a databázové klíče jsou oddělené.
- `NEXT_PUBLIC_` obsahuje pouze hodnoty určené pro veřejný klient.
- Build logy a runtime logy neobsahují hodnoty proměnných.
- Staré, nepoužívané a sdílené klíče jsou odstraněné nebo rotované bezpečným postupem.
- Změna secretu vede k novému deploymentu nebo restartu tam, kde je to potřeba.

Nežádej uživatelku o zkopírování hodnoty. Stačí název, scope a maskovaný konec.

## 8. Deployment Protection a veřejné URL

Vercel vytváří generated deployment URLs. Ty mohou být veřejně dostupné, dokud není zapnutá odpovídající ochrana. Nespoléhej na tvrzení, že konkrétní preview URL musí být zapsaná v Certificate Transparency logu; rizikem je její veřejná dostupnost a objevitelnost přes PR, logy, historii nebo sdílení.

### Zkontroluj

- aktuální metodu ochrany: Vercel Authentication, Password Protection, Trusted IPs nebo jinou aktuální možnost;
- aktuální scope ochrany: preview, generated deployment URLs, staré production deployments a production domains;
- dostupnost podle skutečného plánu v den auditu;
- shareable links, bypass tokeny, automation bypass a exceptions;
- zda ochrana funguje v anonymním okně a na starém deploymentu;
- zda webhook, cron, monitoring a automatizace používají bezpečnou výjimku s minimálním scope;
- zda citlivé preview neobsahuje produkční data.

Ochranu URL nepovažuj za náhradu autentizace uvnitř samotné aplikace.

## 9. Git integrace, build a zdrojový kód

- Ověř připojený repozitář a produkční větev.
- Zkontroluj, kdo může spustit nebo propagovat produkční deployment.
- Ověř Git fork protection a práci se secrets u pull requestů z forků podle aktuálních možností Vercelu.
- Zkontroluj build command a install command; nespouštěj je během auditu bez souhlasu.
- Prověř, zda install/build skript nestahuje a nespouští neověřený kód.
- Ověř dostupnost zdrojových souborů, source maps, build outputu a logů jen oprávněným členům.
- Zkontroluj ignored build step a podmínky, které by mohly nasadit jinou větev, než se očekává.
- Ověř, že produkční deployment odpovídá zaznamenanému commitu.

## 10. Účty, provoz, náklady a obnova

### Účty a tým

- Vlastník a členové mají nejmenší potřebnou roli.
- Bývalí spolupracovníci a staré integrace jsou odebraní.
- Účet má 2FA nebo passkey a bezpečně uložené recovery kódy.
- OAuth/GitHub integrace a deploy hooks mají minimální scope.

### Monitoring a náklady

- Existuje upozornění na výpadek, chybovost a prudkou změnu provozu.
- AI, e-mail, image generation a drahé API mají aplikační limity.
- Ověř budget notifications a dostupné spend controls; neslibuj, že samotný alert zabrání nákladu.
- Veřejná funkce má rate limit, timeout a maximální velikost požadavku.

### Obnova

- Je známý postup rollbacku na předchozí bezpečný deployment.
- Rollback nevrací staré kompromitované secrets nebo nekompatibilní databázové schema.
- Deployment log a commit umožní dohledat, co běží.
- Ověř poslední praktický test obnovy dat a aplikace.

## 11. Povinné testy

Podle rozsahu bezpečně ověř:

1. Chráněná stránka a příslušné API bez session vrátí odmítnutí.
2. Účet A nemůže načíst ani změnit data účtu B.
3. Přímé volání Server Action nebo Route Handleru neobejde UI.
4. Produkční a preview klíče a databáze jsou oddělené.
5. Preview URL je v anonymním okně chráněná podle záměru.
6. Skutečné hlavičky a cookie flags odpovídají konfiguraci.
7. Citlivá odpověď není veřejně nebo sdíleně cachovaná.
8. Produkční URL odpovídá kontrolovanému commitu.
9. Starý deployment nezůstal veřejný s citlivou funkcí.
10. Rollback a monitoring mají známého vlastníka.

## 12. Oficiální zdroje

Před auditem ověř aktuální dokumentaci:

- Next.js Proxy: https://nextjs.org/docs/app/getting-started/proxy
- Next.js security a aktualizace: https://nextjs.org/docs
- Vercel Deployment Protection: https://vercel.com/docs/deployment-protection
- Vercel generated URLs: https://vercel.com/docs/deployments/generated-urls
- Vercel environment variables: https://vercel.com/docs/environment-variables

Do reportu napiš verzi Next.js, datum ověření dokumentace a skutečný Vercel plán/scope. Když dashboard nebo dokumentace neodpovídá očekávání, označ položku jako `NEOVĚŘENO` a nehádej.
