# Supabase

Načti tento modul, když projekt používá Supabase Database, Auth, Storage, Realtime nebo Edge Functions. Nejdřív zjisti, zda projekt používá nové publishable/secret keys, starší `anon`/`service_role`, nebo obojí. Aktuální migrační termíny a dashboard ověř v oficiální dokumentaci v den auditu.

## Obsah

1. Rozpoznání a mapa komponent
2. API klíče
3. Row Level Security a databázová oprávnění
4. Policies a test se dvěma uživateli
5. Views, funkce a RPC
6. Storage
7. Auth
8. Edge Functions a serverové použití
9. Realtime
10. Zálohy, obnova a prostředí
11. Monitoring a provoz
12. Povinné testy
13. Oficiální zdroje

## 1. Rozpoznání a mapa komponent

Hledej:

- `@supabase/supabase-js`, Supabase URL a klienty;
- SQL migrace, `supabase/` složku a generované typy;
- Auth providers, callback URL a session handling;
- Storage buckets a práci s `storage.objects`;
- Edge Functions a jejich ověřování;
- Realtime subscriptions a publications;
- serverový klient se zvýšeným klíčem;
- přímé Postgres connection strings a poolery.

Zmapuj, která část běží v prohlížeči a která na serveru.

## 2. API klíče

### Typy

Supabase používá:

- `sb_publishable_...`: nízká oprávnění, určený pro veřejné klienty; bezpečnost dat zajišťují databázová oprávnění a RLS;
- `sb_secret_...`: zvýšená oprávnění, pouze backend; obchází RLS;
- legacy `anon`: starší nízko-oprávněný klíč;
- legacy `service_role`: starší zvýšený klíč, pouze backend; obchází RLS.

Migrace a termíny legacy klíčů se mohou změnit; ověř aktuální dokumentaci. Nevynucuj migraci během běžného auditu bez plánu a rollbacku.

### Povinné kontroly

- Publishable/anon klíč může být v klientu, ale není tajemství ani autorizační hranice.
- Secret/service_role klíč nesmí být v prohlížeči, mobilním klientu, veřejném zdrojovém kódu, URL, logu ani dokumentaci.
- `NEXT_PUBLIC_`, `VITE_` nebo obdobný klientský prefix nesmí obsahovat secret/service_role.
- Serverová komponenta se zvýšeným klíčem musí před každou operací provést vlastní autentizaci a autorizaci.
- Jeden serverový klíč nesdílej zbytečně mezi nezávislými komponentami; nové secret keys mohou být oddělené a samostatně rotovatelné.
- Při incidentu klíč zneplatni/rotuj podle aktuálního postupu Supabase a zkontroluj použití. Pouhé smazání z gitu nestačí.
- V reportu nikdy nezobrazuj celou hodnotu JWT ani secret key.

### Pozor na klienta a session

- Ověř, jak klient nastavuje `Authorization` header.
- Nemíchej zvýšený serverový klient se session běžného uživatele způsobem, který nepředvídatelně změní roli požadavku.
- Pro administrátorské operace používej oddělený server-only klient a explicitní kontrolu oprávnění.

## 3. Row Level Security a databázová oprávnění

RLS (Row Level Security) jsou pravidla na úrovni řádků. Samotné zapnutí RLS není důkaz, že je vše správně.

### Zkontroluj každou exposed tabulku

1. Je RLS zapnuté?
2. Jaká práva mají role `anon`, `authenticated` a další role přes `GRANT`?
3. Existují policies pro skutečně potřebné operace?
4. Je výchozí stav zakázaný, když policy chybí?
5. Nevystavuje API tabulku, view nebo funkci, která měla být interní?
6. Nezakládá se vlastnictví na hodnotě poslané klientem místo `auth.uid()` nebo jiného ověřeného identity contextu?

Tabulky vytvořené různými cestami mohou mít odlišné defaulty. Nehádej podle toho, zda vznikly v dashboardu nebo migraci; ověř skutečný stav.

### Grants a RLS jsou dvě vrstvy

- `GRANT` určuje, zda role smí operaci vůbec volat.
- RLS určuje, které konkrétní řádky smí operace zasáhnout.

Ověř obě vrstvy. Široké granty s chybnou policy i úzké grants blokující legitimní funkci mohou být problém.

## 4. Policies a test se dvěma uživateli

### Operace odděleně

Prověř zvlášť:

- `SELECT`;
- `INSERT`;
- `UPDATE`;
- `DELETE`.

Policy pro čtení automaticky nechrání změnu.

### Časté chyby

- `USING (true)` nebo `WITH CHECK (true)` u citlivé tabulky;
- kontrola vlastníka při `SELECT`, ale ne při `UPDATE`;
- možnost změnit `user_id`, `owner_id`, `organization_id`, roli nebo stav;
- policy založená na hodnotě z JWT, kterou lze nesprávně ovlivnit;
- chybějící tenant/organization filtr;
- admin výjimka bez serverové kontroly role;
- policy závislá na funkci se zvýšenými právy bez bezpečného `search_path`.

### Povinný test

V bezpečném testovacím prostředí vytvoř:

- účet A s vlastním záznamem;
- účet B s vlastním záznamem.

Ověř pro každý relevantní typ operace, že A nemůže číst, měnit ani mazat data B. Ověř také, že A nemůže při vytvoření nebo změně nastavit vlastníka na B nebo administrátorskou hodnotu.

Použij skutečný klientský/publishable klíč a session uživatele. Test přes secret/service_role klíč neověřuje RLS, protože ho obchází.

## 5. Views, funkce a RPC

### Views

- Ověř, zda view respektuje oprávnění a RLS podle zamýšlené konfigurace.
- Podle verze Postgres/Supabase zvaž `security_invoker`, je-li potřeba, a ověř aktuální chování.
- View nesmí sloučit nebo agregovat data více uživatelů bez filtru.

### RPC a funkce

- Zkontroluj `GRANT EXECUTE` pro každou exposed funkci.
- `SECURITY DEFINER` funkce běží s právy vlastníka; prověř je jako zvýšený serverový endpoint.
- Nastav bezpečný `search_path` a schema-qualified názvy podle doporučení Postgres/Supabase.
- Validuj vstup a autorizaci uvnitř funkce.
- Nepoužívej dynamické SQL s nedůvěryhodným vstupem.
- Ověř, že funkce nevrací více dat, než potřebuje.

## 6. Storage

Databázová záloha a Storage objekty jsou oddělené oblasti. Zkontroluj obě.

### Buckets

- Je bucket veřejný pouze tehdy, když mají být všechny objekty veřejně čitelné?
- Soukromý obsah používej jako výchozí pro uživatelské dokumenty.
- Odděl veřejné marketingové soubory od soukromých uživatelských dat.

### Policies

- Ověř `storage.objects` policies pro čtení, upload, změnu a smazání.
- Uživatel smí pracovat jen se svou složkou nebo objektem podle bezpečně odvozeného identifikátoru.
- Název cesty poslaný klientem nesmí umožnit zapisovat do cizího prostoru.
- Signed URL má krátkou expiraci a vydává se až po autorizaci.
- Uživatel nesmí vygenerovat signed URL pro cizí objekt.

### Obsah

Použij také `file-uploads.md`: typ, velikost, náhodný název, bezpečné stažení, skenování podle rizika a ochranu proti aktivnímu obsahu.

## 7. Auth

Ověř podle použitého flow:

- povolené Site URL a redirect URLs pro development, preview a production;
- zda wildcard redirect neumožní cizí doménu;
- e-mail confirmation, reset hesla a změnu e-mailu;
- expiraci session a refresh tokenů;
- zneplatnění po změně hesla nebo podezření;
- rate limits a ochranu OTP/magic link;
- MFA pro administrátory, je-li dostupná a přiměřená;
- OAuth provider secrets pouze na serverové/platformní straně;
- vlastní email templates bez open redirectu a úniku tokenu;
- user metadata: nepoužívej uživatelem měnitelná metadata jako důvěryhodnou administrátorskou roli.

Role a oprávnění ukládej do důvěryhodného serverového nebo databázového zdroje a kontroluj je při každé citlivé operaci.

## 8. Edge Functions a serverové použití

- Ověř, zda function skutečně autentizuje uživatele a validuje token podle aktuálního Supabase modelu.
- Samotná přítomnost `apikey` headeru nemusí dokazovat identitu uživatele.
- Ověř issuer, audience, expiraci a zamýšlenou roli JWT tam, kde se JWT používá.
- Secret key ve function je zvýšený přístup; každá operace musí mít vlastní autorizaci.
- Nevystavuj obecný admin endpoint „proveď libovolný SQL/Storage úkon“.
- Nastav CORS přesně podle klientů a nepoužívej ho jako autorizaci.
- Validuj tělo, limit velikosti, timeout a rate limit.
- Logy function nesmějí obsahovat Authorization header, session, secret key ani celé osobní payloady.
- Webhook function ověřuje podpis nad raw body, pokud to poskytovatel vyžaduje.

## 9. Realtime

- Zkontroluj, které tabulky jsou v Realtime publication.
- RLS a oprávnění musí odpovídat i realtime odběru.
- Uživatel nesmí odposlouchávat změny cizí organizace nebo záznamu.
- Channel názvy a presence data nesmějí prozrazovat citlivé identifikátory bez potřeby.
- Ověř odpojení, refresh tokenu a chování po změně oprávnění.
- Omez objem událostí a nákladové riziko.

## 10. Zálohy, obnova a prostředí

### Zálohy

Zjisti podle skutečného plánu:

- frekvenci a retenci databázových záloh;
- point-in-time recovery, je-li dostupné;
- kdo smí obnovu spustit;
- poslední test obnovy;
- samostatnou zálohu Storage objektů, pokud jsou důležité;
- export migrací, funkcí, policies a konfigurace Auth.

Neříkej „Supabase zálohuje vše“, dokud není ověřeno, co konkrétní plán a komponenta zahrnuje.

### Prostředí

- Odděl produkční a experimentální projekt, nebo použij bezpečné branching prostředí podle aktuálních možností.
- Preview nepřipojuj k produkční databázi se zvýšeným klíčem.
- Migrace testuj před produkcí a připrav rollback nebo forward-fix.
- Neprováděj destruktivní migraci během auditu.

## 11. Monitoring a provoz

- Projdi Security Advisor a každý nález vysvětli; nedoporuč slepé `Dismiss`.
- Zkontroluj Auth logs, database logs, Edge Function logs a audit události podle dostupnosti.
- Nastav upozornění na chyby, zvýšený provoz a náklady.
- Ověř limity databáze, connection poolu a Edge Functions.
- Přímý Postgres connection string chraň jako secret a omez síťově, pokud je to dostupné a vhodné.
- Odeber staré členy týmu, integrace a klíče.
- Kritický projekt má 2FA/passkey a bezpečnou obnovu účtu.

## 12. Povinné testy

1. Publishable/anon klíč v klientu nemůže bez session číst citlivou tabulku.
2. Účet A nemůže přes klientský API přístup číst ani měnit data B.
3. A nemůže změnit `owner_id`, `organization_id`, roli nebo chráněný stav.
4. Secret/service_role není v klientském bundle ani logu.
5. Serverový endpoint se zvýšeným klíčem odmítne neautorizovaného uživatele.
6. Storage bucket a policies odpovídají veřejnosti obsahu.
7. Signed URL pro cizí objekt nelze získat.
8. Edge Function ověřuje identitu a oprávnění, ne pouze API key.
9. Realtime nepropouští cizí data.
10. Poslední restore test zahrnuje databázi a potřebné Storage objekty.

## 13. Oficiální zdroje

Ověř v den auditu:

- API keys: https://supabase.com/docs/guides/getting-started/api-keys
- Migrace klíčů: https://supabase.com/docs/guides/getting-started/migrating-to-new-api-keys
- Securing the API a RLS: https://supabase.com/docs/guides/api/securing-your-api
- Database privileges: https://supabase.com/docs/guides/database/postgres/roles
- Storage security: https://supabase.com/docs/guides/storage/security/access-control
- Auth security: https://supabase.com/docs/guides/auth
- Backups: https://supabase.com/docs/guides/platform/backups

Do reportu uveď typy aktivních klíčů, ověřený stav RLS/grants a datum dokumentace. Když nemáš přístup do dashboardu nebo SQL metadat, použij `NEOVĚŘENO`.
