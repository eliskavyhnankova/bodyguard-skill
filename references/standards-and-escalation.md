# Standardy, aktuálnost a eskalace

Použít pro vymezení rozsahu auditu, práci s OWASP a rozhodnutí, kdy automatická kontrola nestačí.

## Obsah

1. OWASP Top 10 není úplný audit
2. OWASP ASVS jako základ plného auditu
3. AI standardy
4. Aktuálnost platformních informací
5. Kdy doporučit bezpečnostní specialistku nebo specialistu
6. Kdy doporučit právní nebo privacy specialistku
7. Hranice automatického auditu

## 1. OWASP Top 10 není úplný audit

OWASP Top 10 používat jako přehled nejvýznamnějších kategorií rizik a jako kontrolu, že nebyla přehlédnuta zásadní oblast. Nevydávat průchod Top 10 za certifikaci nebo úplný bezpečnostní audit.

Aktuální vydání vždy ověřit na oficiální stránce:

https://owasp.org/Top10/

## 2. OWASP ASVS jako základ plného auditu

U běžné webové aplikace s přihlášením, více uživateli, osobními údaji nebo citlivou obchodní funkcí použít OWASP Application Security Verification Standard jako systematickou kostru.

- Pro praktický `full` audit použít Level 2 podle aktuální stabilní verze.
- Level 1 použít jen pro velmi jednoduchou a nízkorizikovou aplikaci.
- Level 3 doporučit pro vysoce citlivé, kritické nebo regulované systémy a provést s lidským specialistou.
- Neprohlašovat formální shodu, pokud nebyly všechny relevantní požadavky skutečně ověřeny a doloženy.
- V reportu uvést, které kapitoly byly použity a které nebyly v rozsahu.

Aktuální verzi ověřit zde:

https://owasp.org/www-project-application-security-verification-standard/

## 3. AI standardy

U AI aplikací doplnit aktuální materiály OWASP GenAI Security Project a podle potřeby NIST AI RMF. Neomezit kontrolu na prompt; posoudit oprávnění nástrojů, data, RAG, náklady, modelový supply chain a lidské potvrzení.

- https://genai.owasp.org/
- https://www.nist.gov/itl/ai-risk-management-framework

## 4. Aktuálnost platformních informací

Před konkrétním návodem ověřit:

- verzi frameworku a runtime;
- aktuální názvy konvencí, například Next.js Proxy versus starší Middleware;
- typy klíčů služby, například Supabase publishable/secret a starší anon/service-role;
- dostupnost ochrany podle konkrétního plánu GitHubu nebo Vercelu;
- aktuální cestu v dashboardu;
- podporovanou verzi SDK a oficiální bezpečnostní doporučení.

Používat primární zdroje: oficiální dokumentaci, bezpečnostní advisory a standardy. U technické otázky neodvozovat aktuální stav z blogu třetí strany, pokud je k dispozici primární zdroj.

Když web nebo konektor není dostupný:

- uvést, že klikací cesta nebo dostupnost funkce nebyla aktuálně ověřena;
- popsat cíl nastavení obecně;
- nehádat cenu, tarif ani název tlačítka.

## 5. Kdy doporučit bezpečnostní specialistku nebo specialistu

Doporučit cílený penetrační test nebo odborný audit, když projekt:

- používá vlastní přihlašování, kryptografii, tokenový protokol nebo správu hesel;
- ukládá zdravotní, finanční, dětská, biometrická nebo jinak vysoce citlivá data;
- zpracovává platby nestandardně nebo drží více než běžné tokenizované platební údaje;
- je multi-tenant SaaS pro více zákaznických organizací;
- má veřejné uploady nebo složité parsování souborů;
- obsahuje administraci nad daty mnoha uživatelů;
- zpřístupňuje API třetím stranám nebo používá komplexní OAuth scopes;
- dovoluje AI nebo agentovi posílat zprávy, mazat data, měnit oprávnění, spouštět kód nebo utrácet peníze;
- je významnou součástí firemního provozu nebo může způsobit velkou finanční škodu;
- vykazuje známku skutečného napadení, úniku klíče nebo neoprávněného přístupu;
- potřebuje formální shodu se standardem nebo regulací.

Bodyguard má před odborným auditem:

1. odstranit zjevné blokující chyby;
2. vytvořit mapu architektury a dat;
3. připravit testovací účty a staging;
4. sepsat známé hranice a rizika;
5. dodat commit, deployment a seznam služeb;
6. zachovat logy a důkazy.

## 6. Kdy doporučit právní nebo privacy specialistku

Doporučit právní posouzení, když projekt:

- zpracovává osobní údaje ve významném rozsahu;
- pracuje s dětmi nebo citlivými kategoriemi dat;
- posílá data AI nebo jiným externím poskytovatelům;
- používá biometriku, profilování nebo automatizované významné rozhodování;
- utrpěl možný únik osobních údajů;
- nejasně řeší souhlasy, retenci, export nebo mazání;
- působí ve více jurisdikcích.

Bodyguard může popsat technická fakta, ale nemá hádat právní povinnost, lhůtu nebo výklad.

## 7. Hranice automatického auditu

Automatický skener dobře hledá vzory, ale často nepozná:

- zda je nález skutečně dosažitelný;
- obchodní logiku;
- autorizační pravidla napříč rolemi;
- nastavení mimo repozitář;
- chyby vzniklé až v produkčním deploymentu;
- sociální inženýrství a recovery proces;
- kombinaci více slabších problémů;
- zero-day zranitelnost;
- úmyslnou skrytou logiku v závislosti.

Proto:

- ručně potvrdit každý významný nález;
- oddělit podezření od potvrzeného problému;
- uvést neověřené oblasti;
- nevydávat absolutní záruku;
- po opravě provést re-test.
