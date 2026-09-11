# Reakce na bezpečnostní incident

Načti při podezření na uniklý klíč, veřejně dostupná data, převzatý účet, neobvyklé platby, škodlivý kód nebo aktivní napadení. Prioritou je omezit škodu, zachovat důkazy a bezpečně obnovit provoz. Běžný audit přeruš, pokud pokračování může zhoršit situaci.

## Obsah

1. Základní pravidla
2. Povinný záznam incidentu
3. Rychlé třídění podle typu incidentu
4. Zachování důkazů
5. Ověření rozsahu
6. Bezpečná obnova
7. Komunikace
8. Post-incident kontrola

## Základní pravidla

- Nikdy nezobrazuj celý nalezený secret nebo osobní data.
- Nečisti historii, nemaž logy a nepřepisuj systém dřív, než zachováš potřebné důkazy.
- Nepoužívej možná kompromitovaný účet nebo zařízení pro rotaci, pokud existuje bezpečnější cesta.
- Bez výslovného souhlasu nic nerotuj, nemaž ani neodstavuj; výjimkou je pouze postup výslovně schválený uživatelkou.
- Neprováděj útočné testy proti cizím systémům.
- U vysoce citlivých dat, finanční škody nebo známek aktivního útočníka doporuč okamžitě zapojit bezpečnostního specialistu a podporu poskytovatele.

## Povinný záznam incidentu

Zapiš bez tajných hodnot:

- ID incidentu, datum, čas a časové pásmo;
- kdo incident zjistil;
- projekt, prostředí, doménu a dotčené služby;
- co bylo nalezeno a kde;
- typ tajemství nebo dat;
- první známý a poslední možný čas expozice;
- zda byl repozitář, URL nebo bucket veřejný;
- co již bylo změněno;
- kdo je vlastníkem dalšího kroku.

Pro soubory a logy lze zaznamenat hash, cestu, velikost a čas. Nekopíruj citlivý obsah zbytečně.

## Rychlé třídění

### A. Možný únik klíče nebo tokenu

Postupuj v tomto pořadí:

1. Maskuj hodnotu a urč typ, poskytovatele, scope a prostředí.
2. Zjisti, zda mohl být secret veřejný, sdílený nebo commitnutý v historii.
3. Považuj ho za kompromitovaný, dokud není prokázán opak.
4. Z bezpečného účtu zneplatni nebo rotuj secret podle oficiálního postupu poskytovatele.
5. Vytvoř náhradní klíč s nejmenším potřebným oprávněním.
6. Aktualizuj bezpečný secret store a všechna závislá prostředí.
7. Znovu nasaď nebo restartuj pouze potřebné komponenty.
8. Ověř, že starý klíč již nefunguje a nový funguje v očekávaném rozsahu.
9. Prověř audit logy, použití, náklady, přihlášení, nové účty, změny a exporty od prvního možného úniku.
10. Až potom odstraň hodnotu ze současného kódu a podle potřeby čistěte historii.
11. Zkontroluj forks, caches, CI logs, artifacts, issues, PR, screenshoty a další kopie.
12. Přidej ochranu proti opakování: secret scanning, push protection, oddělené klíče, expiraci a dokumentovaný postup rotace.

### B. Veřejná databáze, tabulka, bucket nebo soubor

1. Omez veřejný přístup nejmenší bezpečnou změnou.
2. Zabraň dalšímu zápisu a exportu, pokud je to potřeba.
3. Zachovej konfiguraci, logy a časovou osu před většími změnami.
4. Zjisti, která data byla dostupná a po jakou dobu.
5. Prověř access logs, signed URLs, CDN cache, realtime a staré deploymenty.
6. Ověř, zda útočník data pouze četl, nebo také změnil či smazal.
7. Rotuj související klíče, pokud mohly uniknout nebo umožňovaly přístup.
8. Oprav RLS, grants, storage policies a serverovou autorizaci.
9. Otestuj dva účty a anonymní přístup.
10. Posuď povinnost informovat dotčené osoby, zákazníky, poskytovatele nebo úřady s právní/DPO podporou podle typu dat a jurisdikce.
11. Obnov poškozená data z ověřené zálohy a zkontroluj integritu.

### C. Převzatý účet GitHubu, Vercelu, registrátora, databáze nebo jiné služby

1. Použij důvěryhodné zařízení a oficiální recovery/support cestu.
2. Změň heslo a zapni nebo obnov 2FA/passkey.
3. Odhlás všechny sessions, pokud služba umožňuje.
4. Zkontroluj recovery e-mail, telefon a záložní kódy.
5. Odeber neznámé členy, OAuth apps, GitHub Apps, PAT, SSH keys, deploy keys a API tokens.
6. Zkontroluj audit log: přihlášení, změny rolí, secrets, DNS, deployments, webhooks a billing.
7. Rotuj klíče, které mohl účet zobrazit nebo změnit.
8. U domény zkontroluj nameservery, DNS záznamy, registrar lock a transfer stav.
9. U repozitáře zkontroluj commity, tags, releases, workflow, branch rules a artifacts.
10. U hostingu zkontroluj všechny deploymenty, environment variables, domains a bypass výjimky.
11. U plateb zkontroluj payouts, bankovní údaje, refundace a webhook destinations.

### D. Podezření na škodlivý kód nebo aktivního útočníka

1. Neprováděj náhodné příkazy v kompromitovaném prostředí.
2. Omez přístup nebo provoz bezpečným způsobem; podle dopadu může být vhodné maintenance/odstavení.
3. Zachovej snapshot, logy, procesy, síťové události, commit/deployment ID a časovou osu.
4. Rotuj credentials z čistého prostředí, ne z kompromitovaného hostu.
5. Zkontroluj persistence: nové účty, cron, workflow, webhooks, deploy hooks, startup scripts, dependencies a DNS.
6. Porovnej běžící artefakt s důvěryhodným commitem.
7. Obnov z čistého, ověřeného zdroje; nepoužívej pouze „opravený“ kompromitovaný server bez jistoty.
8. Po obnově sleduj opakované indikátory a neobvyklý provoz.
9. Zapoj specialistu, pokud není jasný rozsah nebo cesta průniku.

## Zachování důkazů

Před změnou, je-li to bezpečné a přiměřené:

- exportuj relevantní audit a access logy;
- ulož seznam členů, tokenů, integrací, deploymentů a konfigurace;
- zaznamenej commit SHA, deployment ID a hash podezřelého souboru;
- uchovej screenshot nastavení bez zobrazení secretu;
- zapisuj přesný čas každého zásahu;
- nastav kopii důkazů jako read-only a omez přístup.

Nezveřejňuj důkazy v běžném chatu, issue nebo veřejném repozitáři.

## Ověření rozsahu

Ptej se:

- Jaké oprávnění měl uniklý klíč?
- Byl použit v produkci, preview nebo obojím?
- Kde všude byl uložen nebo zkopírován?
- Mohl číst, měnit, mazat nebo utrácet?
- Existují logy a jaká je jejich retence?
- Byl klíč použit z neznámé IP, regionu, user agentu nebo v neobvyklém čase?
- Vznikly nové klíče, uživatelé, webhooky, deployments, DNS záznamy nebo transakce?
- Došlo k exportu nebo změně osobních dat?
- Je stále aktivní cesta, kterou incident vznikl?

Absenci logu nevykládej jako důkaz, že ke zneužití nedošlo.

## Bezpečná obnova

1. Odstraň kořenovou příčinu.
2. Ověř nové secrets a nejmenší oprávnění.
3. Ověř autorizaci a oddělení uživatelů.
4. Obnov data z ověřené zálohy, je-li potřeba.
5. Ověř integritu databáze, souborů, workflow a DNS.
6. Nasaď konkrétní důvěryhodný commit.
7. Proveď cílené bezpečné testy.
8. Zapni zvýšený monitoring a alerty.
9. Dokumentuj zbytková rizika a vlastníka.
10. Neuzavírej incident pouze proto, že aplikace znovu funguje.

## Komunikace

- Odděl ověřená fakta, předpoklady a neznámé.
- Neslibuj, že „nic neuniklo“, když to logy neumějí prokázat.
- Sdílej minimum citlivých detailů podle role příjemce.
- U zákazníků popiš konkrétní dopad, čas, přijatá opatření a doporučený krok bez zbytečného technického žargonu.
- Právní povinnosti, oznamovací lhůty a formulaci komunikace ověř s právníkem nebo DPO podle konkrétní jurisdikce a dat.

## Post-incident kontrola

Po stabilizaci vytvoř:

- časovou osu;
- kořenovou příčinu;
- rozsah a dopad;
- seznam rotovaných přístupů;
- důkaz obnovy;
- opatření proti opakování;
- vlastníka a termín každého opatření;
- datum následného auditu.

Nález označ `OVĚŘENĚ VYŘEŠENO` až po cíleném testu a kontrole logů/konfigurace. Čištění historie bez zneplatnění klíče není vyřešení.
