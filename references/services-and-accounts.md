# Externí služby, účty, doména, e-mail a SMS

Použít při režimu `services`, `release` nebo `full`. Nejprve zjistit, které služby projekt skutečně používá. Neptat se na všechny dashboardy bez důvodu.

## Obsah

1. Společný model kontroly služby
2. Účty, hesla, 2FA a recovery
3. Klíče, tokeny a integrace
4. Oddělení prostředí
5. Doména, registrátor a DNS
6. E-mailové služby
7. SMS a komunikační služby
8. Webhooky a callbacky
9. Monitoring, náklady a obnova
10. Jak vést otázky se začátečnicí

## 1. Společný model kontroly služby

U každé kritické služby ověřit šest oblastí:

1. Vlastník a přístupy: kdo je owner, kdo je člen a kdo už přístup nepotřebuje?
2. Přihlášení a recovery: 2FA nebo passkey, recovery kódy, bezpečný recovery e-mail?
3. Klíče a integrace: jaká oprávnění mají, kde jsou použité, lze je samostatně rotovat?
4. Prostředí: oddělení vývoje, preview, stagingu a produkce?
5. Upozornění a náklady: kdo se dozví o chybě, útoku, výpadku nebo překročení rozpočtu?
6. Obnova: lze obnovit účet, data, doménu, konfiguraci a poslední bezpečnou verzi?

Výsledek každé oblasti označit jako ověřeno, nález, podezření, neověřeno nebo netýká se. Odpověď „mám to nastavené“ není důkaz; podle možnosti ověřit konkrétní obrazovku, export nebo živé chování.

## 2. Účty, hesla, 2FA a recovery

- Používat správce hesel a unikátní dlouhé heslo.
- Preferovat passkey nebo phishing-resistant 2FA tam, kde je dostupná.
- SMS 2FA je obvykle lepší než žádná, ale u kritických účtů preferovat bezpečnější metodu.
- Recovery kódy uložit mimo službu, ideálně do správce hesel a podle významu i do bezpečné zálohy.
- Recovery e-mail nesmí být jediný účet na doméně, kterou stejná služba spravuje, bez alternativy.
- Zkontrolovat aktivní session, zařízení a nedávná přihlášení.
- Odebrat bývalé spolupracovníky a staré účty.
- Mít nejméně dva bezpečné vlastníky kritické firemní služby, pokud to snižuje riziko ztráty přístupu; současně omezit nadbytečné vlastníky.
- Nepoužívat sdílené osobní přihlášení, pokud služba podporuje samostatné členy a role.
- Ověřit, kdo zaplatí a obnoví tarif, když hlavní vlastník není dostupný.

## 3. Klíče, tokeny a integrace

- Vést inventář klíčů bez ukládání hodnot do běžné poznámky: služba, název, účel, prostředí, vlastník, scopes, datum vytvoření, expirace a místo použití.
- Každá integrace má nejmenší scopes a přístup jen k potřebným projektům.
- Staré, neznámé nebo nepoužívané klíče zneplatnit po ověření, že nejsou aktivní.
- Preferovat krátkodobé nebo OIDC credentials před dlouhodobým univerzálním klíčem, pokud je řešení podporuje.
- Klíče neposílat e-mailem, chatem, ticketem, screenshotem nebo URL.
- Rotaci plánovat tak, aby bylo možné krátce provozovat starý a nový klíč nebo bezpečně rollbackovat.
- Po rotaci ověřit, že starý klíč skutečně nefunguje.
- OAuth a marketplace integrace pravidelně projít a odebrat nepotřebné.
- Webhook secret a API secret nepoužívat jako stejnou hodnotu.

## 4. Oddělení prostředí

- Vývoj, preview, staging a produkce mají samostatné secrets, databáze nebo bezpečně oddělené datasety podle rizika.
- Testovací e-mail a SMS nejdou reálným kontaktům.
- Testovací platba nepoužívá live účet.
- Preview aplikace nemá širší přístup než produkce.
- Produkční data nekopírovat do testu bez anonymizace a omezení.
- Environment variable scope ověřit v dashboardu, ne jen podle názvu.
- Stará preview prostředí a branch-specific secrets uklidit.
- Změna v jednom prostředí nesmí nečekaně přepsat ostatní.

## 5. Doména, registrátor a DNS

Přístup k registrátorovi nebo DNS umožňuje přesměrovat celý web a e-mail.

### Účet a vlastnictví

- Registrátor a DNS provider mají 2FA nebo passkey.
- Použít unikátní heslo a bezpečný recovery e-mail.
- Doména má správného vlastníka, aktuální kontakty a více než jednu cestu obnovy.
- Zapnout auto-renew, ověřit platební metodu a upozornění na expiraci.
- Použít registrar lock; registry lock zvážit u velmi důležité domény, pokud je dostupný.
- Přístupy bývalých dodavatelů odebrat.

### DNS záznamy

- Nameservery odpovídají zamýšlenému providerovi.
- Odstranit staré A, AAAA, CNAME, TXT a MX záznamy po ověření dopadu.
- Zkontrolovat dangling CNAME nebo jiný záznam směřující na zrušenou službu; může umožnit převzetí subdomény.
- `robots.txt` ani neznámá subdoména není ochrana.
- DNSSEC zapnout jen s podporou registrátora i DNS providera a se známým postupem při změně nameserverů.
- CAA může omezit certifikační autority; není automaticky povinné pro malý projekt.
- TTL plánovat před migrací; neprovádět náhlou změnu bez rollbacku.

### E-mailová doména

- SPF, DKIM a DMARC odpovídají skutečným odesílatelům.
- Staré ověřovací TXT záznamy a nepoužívané odesílací služby odstranit po ověření.
- MX a recovery e-mail zůstanou funkční při změně webového hostingu.

## 6. E-mailové služby

- API key je pouze na serveru a má nejmenší oprávnění.
- Endpoint pro odeslání vyžaduje autorizaci a rate limit.
- Uživatel nemůže změnit příjemce, sender, reply-to nebo template na libovolnou hodnotu bez validace.
- Chránit proti header injection v názvu, předmětu a adresách.
- HTML šablonu escapovat nebo sanitizovat; uživatelský obsah nevkládat jako raw HTML.
- Preview a test používat sandbox, allowlist příjemců nebo bezpečné přesměrování.
- Hromadné odesílání má kvóty, unsubscribe a ochranu před opakováním.
- Odhlašovací a preference odkazy jsou podepsané, mají úzký účel a neumožní změnit cizí účet.
- E-mailové logy neobsahují hesla, reset tokeny ani celý citlivý obsah.
- SPF, DKIM a DMARC ověřit v DNS podle skutečného poskytovatele.
- Monitoring upozorní na nárůst bounce, complaint, blokaci domény nebo nečekané množství odeslaných zpráv.

## 7. SMS a komunikační služby

- API key je server-only.
- Odeslání vyžaduje autentizaci, autorizaci, rate limit a cenový limit.
- OTP má krátkou expiraci, omezený počet pokusů a nelze ho znovu použít.
- Telefonní číslo normalizovat a ověřit.
- Test neposílá na reálná čísla bez výslovného záměru.
- Uživatel nemůže použít endpoint jako otevřenou SMS bránu.
- Nastavit spend alerts a geografická omezení podle cílového trhu.
- Logy neobsahují celý OTP ani zbytečný obsah zprávy.
- Webhook doručení ověřuje podpis a je idempotentní.

## 8. Webhooky a callbacky

Obecně pro každou službu:

- Ověřit podpis podle oficiálního SDK a nad správnou podobou raw body.
- Použít správný secret pro správné prostředí.
- Uložit stabilní event ID a zpracovat událost idempotentně.
- Počítat s duplicitou, zpožděním a jiným pořadím.
- Omezit allowlist typů událostí.
- Dlouhou práci přesunout do fronty; rychle potvrdit bezpečné přijetí.
- Nevěřit payloadu jako důkazu vlastnictví bez vazby na lokální data.
- Callback URL a OAuth redirect jsou přesné nebo allowlistované.
- Tajemství nevkládat do query parametru.
- Testovací webhook nesmí měnit produkční data.

## 9. Monitoring, náklady a obnova

### Monitoring

- Kritické služby mají status alert a kontakt, který upozornění čte.
- Zaznamenat změny členů, klíčů, DNS, deploymentu a plateb podle možností služby.
- Ověřit alert testovacím signálem.
- Retence logů stačí k vyšetření incidentu.

### Náklady

- Nastavit budget nebo spend alerts.
- Omezit veřejné a drahé endpointy.
- Ověřit, kdo může zvýšit tarif, limit nebo počet prostředků.
- Zkontrolovat staré projekty, preview, storage, log drains a nevyužité zdroje.
- Nárůst nákladů považovat i za možný bezpečnostní signál.

### Obnova

- Znát postup obnovy účtu a kontaktní údaje podpory.
- Mít export kritické konfigurace, pokud služba dovoluje.
- Ověřit zálohu databáze, souborů a DNS odděleně.
- Mít poslední bezpečný deployment a rollback.
- Recovery plán nesmí záviset jen na jediném zařízení nebo člověku.

## 10. Jak vést otázky se začátečnicí

1. Nejprve zjistit službu z kódu nebo konektoru.
2. Ptát se po jedné tematické skupině, ne dvanáct otázek najednou.
3. Dovolit odpověď „nevím“.
4. Před uvedením přesné cesty v dashboardu ověřit aktuální oficiální dokumentaci nebo UI.
5. Nežádat uživatelku, aby poslala hodnotu klíče, hesla, cookie nebo recovery kódu.
6. Po každé skupině shrnout: ověřeno, chybí, proč to vadí a kde to bezpečně nastavit.
7. Když přístup není dostupný, označit oblast jako `NEOVĚŘENO`, ne jako bezpečnou.

Doporučený úvod:

> Potřebuji ověřit nastavení služby, které není vidět v kódu. Neposílej mi žádné heslo ani hodnotu klíče. Stačí název nastavení, stav zapnuto/vypnuto nebo bezpečný screenshot s maskovanými hodnotami.
