# GitHub a CI/CD

Načti tento modul, když je kód na GitHubu nebo projekt používá GitHub Actions. Stav funkcí, názvy sekcí a dostupnost podle typu účtu vždy ověř v aktuální oficiální dokumentaci a přímo v repozitáři.

## Obsah

1. Viditelnost repozitáře
2. Tajemství a Secret Scanning
3. Dependabot a Code Scanning
4. Větve, pull requesty a vydávání
5. GitHub Actions
6. Účty, tokeny, klíče a aplikace
7. Spolupracovníci a organizace
8. Povinné testy
9. Oficiální zdroje

## 1. Viditelnost repozitáře

Veřejný repozitář není automaticky bezpečnostní chyba a soukromý repozitář není trezor na secrets.

Ověř:

- zda veřejnost odpovídá záměru projektu;
- zda veřejný repozitář neobsahuje osobní data, interní dokumenty, neveřejné endpointy, tajné obchodní instrukce nebo credentials;
- zda soukromý repozitář nemá zbytečně široký seznam spolupracovníků;
- zda forks, templates, archived kopie nebo staré repozitáře neobsahují dřívější secrets;
- zda GitHub Pages, releases, artifacts, packages a Actions logs nepublikují citlivý obsah.

Nedoporučuj automaticky privatizaci jako opravu uniklého klíče. Klíč je nutné zneplatnit nebo rotovat.

## 2. Tajemství a Secret Scanning

### Dostupnost

Dostupnost Secret Scanning, Secret Protection, push protection, generic patterns a validity checks se liší podle veřejnosti repozitáře, vlastníka, organizace a plánu. Nikdy netvrď obecně „private je placené“ bez ověření konkrétního účtu.

### Ověř

- zda GitHub secret scanning skutečně běží pro daný repozitář;
- zda jsou zapnuté user alerts, push protection a případně generic/non-provider patterns, pokud jsou dostupné;
- zda nejsou otevřené nebo ignorované alerty;
- proč byl alert případně dismissed a kdo rozhodnutí schválil;
- zda validity check neodesílá citlivou hodnotu způsobem, se kterým uživatelka nesouhlasí;
- zda se secrets neobjevují v issues, PR komentářích, Discussions, gistech, Actions logs, artifacts nebo releases;
- zda lokální `.env` není sledovaný gitem a zda historie neobsahuje dřívější hodnotu.

Když funkce není dostupná, použij lokální read-only sken `scripts/safe_secret_scan.py --history`. Můžeš doporučit prověřený lokální nástroj, například gitleaks nebo trufflehog, ale nic neinstaluj a neposílej kód třetí straně bez souhlasu.

### Reakce na nález

1. Hodnotu v reportu maskuj.
2. Klíč okamžitě zneplatni nebo rotuj podle `incident-response.md`.
3. Zkontroluj audit log a použití.
4. Nahraď hodnotu v bezpečném secret store.
5. Teprve potom řeš historii.

## 3. Dependabot a Code Scanning

Ověř podle dostupnosti:

- Dependabot alerts;
- Dependabot security updates;
- pravidelné version updates s rozumným plánem;
- code scanning/CodeQL nebo jiný SAST nástroj;
- výsledky a nevyřešené alerty;
- zda sken pokrývá výchozí větev a pull requesty;
- zda workflow po selhání bezpečnostního skenu nepokračuje do produkce;
- zda není vše ignorované kvůli falešným poplachům bez dokumentace.

Automatický alert nepovažuj za potvrzenou zranitelnost. Ověř dosažitelnost a dopad. Stejně tak absence alertu neznamená bezpečí.

## 4. Větve, pull requesty a vydávání

Zkontroluj výchozí a produkční větev:

- ochranu před force push a smazáním;
- požadované status checks;
- review tam, kde projekt má další spolupracovníky;
- omezení přímého push do produkční větve;
- podepsané commity nebo tagy tam, kde je vysoký dopad;
- release/tag workflow a vazbu na konkrétní commit;
- deployment environments a případné schválení produkce;
- možnost rollbacku a dohledatelnost posledního bezpečného release.

U sólo projektu nastav přiměřenou ochranu bez zbytečné administrativy. Minimálně zabraň omylu, kdy nedůvěryhodná větev získá produkční secrets nebo automaticky nasadí produkci.

## 5. GitHub Actions

Workflow soubory v `.github/workflows/` považuj za kód s vysokými oprávněními.

### Oprávnění

- Nastav `permissions` pro `GITHUB_TOKEN` na nejmenší potřebný rozsah, ideálně read-only jako výchozí.
- Zvyšuj oprávnění jen konkrétnímu jobu.
- Pro cloud preferuj krátkodobé OIDC přihlášení před dlouhodobým cloudovým klíčem, pokud služba podporuje.
- Produkční environment secrets zpřístupni jen schválenému workflow a větvi.

### Nedůvěryhodné pull requesty

- Zvlášť prověř `pull_request_target`; běží v kontextu základního repozitáře a může mít zvýšená oprávnění.
- Nekontroluj out kód z nedůvěryhodného PR a následně ho nespouštěj v jobu se secrets.
- Neumisťuj uživatelský obsah přímo do shellu, například title, branch, label nebo comment bez bezpečného předání přes environment variable a správného quoting.
- Secrets neposkytuj workflow z nedůvěryhodného forku.
- Self-hosted runner nepoužívej pro nedůvěryhodný veřejný PR bez silné izolace a jednorázového prostředí.

### Externí actions a supply chain

- Externí action u citlivého workflow připni na plný commit SHA nebo jinou důvěryhodnou neměnnou referenci; sleduj aktualizace.
- Prověř vydavatele, údržbu a rozsah action.
- Nepoužívej neznámou action pouze proto, že ji navrhl AI nástroj.
- Zkontroluj Docker images, download skripty a binární soubory.
- Omez retention artifacts a logů; artifact může obsahovat build, source maps nebo `.env`.

### Logy

- Nepoužívej `set -x` kolem secrets.
- Maskování GitHubu nepovažuj za stoprocentní ochranu transformovaných hodnot.
- Nevypisuj celé environment, requesty nebo konfigurační soubory.
- Zkontroluj staré logy a artifacts po incidentu.

## 6. Účty, tokeny, klíče a aplikace

### Osobní účet

- Zapni 2FA nebo passkey.
- Ulož recovery kódy mimo GitHub, ideálně do správce hesel.
- Ověř bezpečný recovery e-mail.
- Zkontroluj aktivní sessions a security log při podezření.

### Přístupy

Prověř:

- personal access tokens, zejména classic PAT;
- fine-grained PAT a jejich repo/scope/expiraci;
- SSH keys a GPG/signing keys;
- deploy keys;
- OAuth Apps a GitHub Apps;
- browser extensions a lokální credential helper;
- staré tokeny v CI, Vercelu, IDE a automatizacích.

Každý přístup má mít vlastníka, účel, nejmenší scope a datum revize. Nepoužívaný přístup odeber.

## 7. Spolupracovníci a organizace

- Zkontroluj owners, outside collaborators, teams a repository roles.
- Odeber bývalé spolupracovníky a staré bot účty.
- Kritickou organizaci nenechávej závislou na jediném ownerovi bez bezpečné obnovy.
- Ověř pravidla 2FA/passkey a audit log, pokud jsou dostupné.
- Zkontroluj third-party access policy, installed GitHub Apps a schválené OAuth apps.
- Secrets sdílej na nejnižší potřebné úrovni: environment/repository před organization, pokud není nutné širší použití.
- Zkontroluj rulesets a výjimky; administrátor nesmí nevědomky obcházet všechny ochrany.

## 8. Povinné testy

Podle rozsahu dolož:

1. Výsledek secret scanning nebo lokálního history scanu bez zobrazení hodnot.
2. Stav nevyřešených Dependabot/Code Scanning alertů.
3. Oprávnění `GITHUB_TOKEN` v každém citlivém workflow.
4. Chování workflow pro PR z forku.
5. Vazbu production deploymentu na konkrétní commit a větev.
6. Seznam lidí a aplikací s write/admin přístupem.
7. 2FA/passkey a bezpečnou recovery cestu kritických vlastníků.
8. Retenci a obsah artifacts/logů.

## 9. Oficiální zdroje

Ověř v den auditu:

- Secret scanning: https://docs.github.com/en/code-security/concepts/secret-security/secret-scanning
- Push protection: https://docs.github.com/en/code-security/secret-scanning/protecting-pushes-with-secret-scanning
- GitHub Actions security: https://docs.github.com/en/actions/security-for-github-actions
- Secure use of `pull_request_target`: https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target
- Dependabot: https://docs.github.com/en/code-security/dependabot
- Code scanning: https://docs.github.com/en/code-security/code-scanning

Do reportu uveď, co bylo skutečně dostupné pro konkrétní typ účtu a plán. Neopisuj staré ceny nebo nabídku z paměti.
