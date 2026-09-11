# Povinná struktura reportu

Použij tento formát při `release`, `full`, `services`, `verify` a `incident`. U `quick` můžeš report zkrátit, ale zachovej rozsah, stavy, důkazy a zákaz celkové zelené.

Nepoužívej barevné emoji jako jediný nositel významu. Nepiš „projekt je bezpečný“. Používej textové verdikty a přesně odděluj ověřené, podezřelé a neověřené oblasti.

## Obsah

1. Hlavička auditu
2. Rozhodnutí o nasazení
3. Pět nejdůležitějších kroků
4. Rozsah a pokrytí
5. Souhrn nálezů
6. Detail každého nálezu
7. Ověřené ochrany
8. Neověřené oblasti a zbytkové riziko
9. Akční plán
10. Co se uživatelka naučila
11. Záznam ověření oprav
12. Příklad nálezu

## 1. Hlavička auditu

```markdown
# Bodyguard: bezpečnostní kontrola [název projektu]

Datum a čas: [ISO datum, časové pásmo]
Režim: [quick / release / full / services / verify / incident / fix]
Repozitář nebo cesta: [hodnota]
Větev: [hodnota / NEOVĚŘENO]
Commit: [SHA / NEOVĚŘENO]
Stav pracovního stromu: [čistý / změny / NEOVĚŘENO]
Prostředí: [lokální / preview / staging / produkce]
Kontrolovaná URL: [URL / NETÝKÁ SE / NEOVĚŘENO]
Použité zdroje: [kód, GitHub, dashboardy, živá URL, rozhovor]
```

## 2. Rozhodnutí o nasazení

Použij přesně jeden stav:

- `BLOKOVÁNO`
- `PODMÍNĚNĚ PŘIPRAVENO`
- `PŘIPRAVENO V OVĚŘENÉM ROZSAHU`
- `NELZE ROZHODNOUT — CHYBÍ KRITICKÉ INFORMACE`
- U `quick`: `RYCHLÁ KONTROLA — NENÍ TO VERDIKT K PRODUKCI`

Šablona:

```markdown
## Rozhodnutí o nasazení: [stav]

[Jedna až tři věty běžnou češtinou: zda nasazovat, co rozhodnutí blokuje a jak významné jsou mezery.]

Důvod rozhodnutí:
- Kritické otevřené nálezy: [počet]
- Vysoké otevřené nálezy: [počet]
- Klíčové neověřené oblasti: [výčet / žádné]
- Největší zbytkové riziko: [věta]
```

Zelený verdikt je povolen pouze podle pravidel v `SKILL.md`. Když chybí commit, deployment, autorizace, produkční databáze nebo platby relevantní pro projekt, zelenou nevydávej.

## 3. Co udělat nejdřív

Uveď nejvýše pět kroků, seřazených podle rizika a závislostí:

```markdown
## Pět nejdůležitějších kroků

1. [konkrétní krok, vlastník, kdy]
2. ...
```

Při uniklém secretu je prvním krokem zneplatnění/rotace, ne čištění historie.

## 4. Rozsah a pokrytí

Odděl tři vrstvy:

```markdown
## Rozsah a pokrytí

| Vrstva | Co bylo kontrolováno | Stav | Důkaz nebo omezení |
|---|---|---|---|
| Kód | ... | OVĚŘENO / ČÁSTEČNĚ / NEOVĚŘENO | ... |
| Služby | ... | ... | ... |
| Živá aplikace | ... | ... | ... |
```

Dále uveď relevantní oblasti:

```markdown
| Oblast | Stav kontroly | Stručný výsledek |
|---|---|---|
| Tajemství | OVĚŘENO / NÁLEZ / PODEZŘENÍ / NEOVĚŘENO / NETÝKÁ SE | ... |
| Autentizace | ... | ... |
| Autorizace | ... | ... |
| Relace a CSRF | ... | ... |
| Vstupy a injekce | ... | ... |
| Uploady | ... | ... |
| Platby | ... | ... |
| AI | ... | ... |
| Závislosti a CI/CD | ... | ... |
| Logy a monitoring | ... | ... |
| Zálohy a obnova | ... | ... |
| Limity a náklady | ... | ... |
```

Nevynechávej relevantní oblast jen proto, že ji nebylo možné zkontrolovat. Označ ji `NEOVĚŘENO` a vysvětli, co chybí.

## 5. Souhrn nálezů

```markdown
## Souhrn nálezů

| ID | Závažnost | Jistota | Oblast | Krátký název | Stav opravy |
|---|---|---|---|---|---|
| BG-001 | KRITICKÁ | VYSOKÁ | Tajemství | ... | OTEVŘENO |
```

ID zachovej stejné mezi prvním reportem a režimem `verify`. Novému nálezu přiděl nové číslo; nepřečíslovávej staré.

## 6. Detail každého nálezu

Použij tuto přesnou strukturu:

```markdown
## BG-### — [krátký název]

Oblast: [například Autorizace]
Vrstva: [KÓD / SLUŽBA / ŽIVÁ APLIKACE / VÍCE VRSTEV]
Závažnost: [KRITICKÁ / VYSOKÁ / STŘEDNÍ / NÍZKÁ]
Jistota: [VYSOKÁ / STŘEDNÍ / NÍZKÁ]
Stav kontroly: [NÁLEZ / PODEZŘENÍ]
Stav opravy: [OTEVŘENO / OPRAVA NAVRŽENA / OPRAVA PROVEDENA, NEOVĚŘENA / OVĚŘENĚ VYŘEŠENO / RIZIKO VĚDOMĚ PŘIJATO]

Co jsem kontrolovala:
[Co tato ochrana dělá a proč se kontroluje.]

Důkaz:
[Soubor:řádek, commit, endpoint, maskovaný typ hodnoty, nastavení nebo přesný výstup nástroje. Neuvádět secret.]

Co jsem očekávala:
[Bezpečné očekávané chování.]

Co jsem našla:
[Konkrétní fakt. Oddělit fakt od odhadu.]

Co se může stát:
[Praktický scénář a dopad běžnou češtinou.]

Proč to vadí:
[Krátké vysvětlení; přirovnání pouze tehdy, když pomůže.]

Jak to opravit:
1. [minimální bezpečný krok]
2. [další krok]

Riziko opravy a rollback:
[Co může změna rozbít a jak se vrátit. U nerizikové změny napsat „Nízké; ...“.]

Jak ověřit opravu:
[Reprodukovatelný test, očekávaný status/odpověď a kontrolované prostředí.]

Do budoucna si pamatuj:
[Jedna krátká obecná zásada.]

Zdroje:
[Relevantní oficiální dokumentace a datum ověření, pokud je tvrzení verzově závislé.]
```

### Důkazní pravidla

- Neuváděj zranitelnost bez místa nebo reprodukovatelného chování.
- Výstup regexu označ jako `PODEZŘENÍ`, dokud není potvrzen kontext.
- Screenshot nastavení bez možnosti ověřit runtime může potvrdit konfiguraci služby, ne chování aplikace.
- Absence nálezu ze skeneru není důkaz bezpečí.
- `OVĚŘENO` musí uvést, jaká kontrola skutečně proběhla.

## 7. Ověřené ochrany

Neuváděj vágní „vše ostatní je v pořádku“. Uveď jen skutečně provedené kontroly:

```markdown
## Ověřené ochrany

- OVĚŘENO: [ochrana] — [důkaz/test]
- OVĚŘENO: ...
```

Když je seznam dlouhý, seskup ho podle oblasti.

## 8. Neověřené a zbytkové riziko

```markdown
## Neověřené oblasti a zbytkové riziko

- NEOVĚŘENO: [oblast] — chybí [přístup/informace/test]. Dopad na verdikt: [ano/ne a proč].
- RIZIKO VĚDOMĚ PŘIJATO: [ID] — vlastník [jméno/role], důvod [...], revize [datum].
```

Neznámou oblast nepopisuj jako bezpečnou.

## 9. Akční plán

```markdown
## Akční plán

### Udělat před nasazením
- [ ] [BG-###] [konkrétní krok] — vlastník: [role/jméno]

### Udělat brzy
- [ ] ...

### Zlepšit později
- [ ] ...

### Po opravách znovu ověřit
- [ ] [BG-###] [přesný test]
```

## 10. Co se uživatelka naučila

```markdown
## Co ses při této kontrole naučila

- [princip použitelný i jinde]
- [princip]
- [princip]
```

Neopakuj pouze seznam chyb. Vysvětli přenositelné zásady.

## 11. Záznam ověření oprav

V režimu `verify` použij:

```markdown
## Ověření oprav

| ID | Původní problém | Co se změnilo | Provedený test | Výsledek | Nový stav |
|---|---|---|---|---|---|
| BG-001 | ... | ... | ... | PROŠLO / NEPROŠLO / NELZE OVĚŘIT | OVĚŘENĚ VYŘEŠENO / OTEVŘENO / OPRAVA PROVEDENA, NEOVĚŘENA |
```

Neuzavírej nález pouze podle tvrzení „už jsem to opravila“ nebo podle existence nového kódu. Ověř stejnou cestu, která problém odhalila.

## 12. Příklad jednoho nálezu

```markdown
## BG-014 — Uživatel může načíst cizí projekt změnou ID

Oblast: Autorizace
Vrstva: VÍCE VRSTEV
Závažnost: VYSOKÁ
Jistota: VYSOKÁ
Stav kontroly: NÁLEZ
Stav opravy: OTEVŘENO

Co jsem kontrolovala:
Zda přihlášený uživatel může načíst pouze své projekty.

Důkaz:
`src/app/api/projects/[id]/route.ts:31-44`; testovací účet A obdržel HTTP 200 pro projekt účtu B.

Co jsem očekávala:
Server po přihlášení ověří také vlastníka projektu a cizí záznam nevydá.

Co jsem našla:
Endpoint ověřuje platnou session, ale dotaz filtruje pouze podle `project.id`.

Co se může stát:
Libovolný přihlášený člověk může zkoušet jiná ID a číst projekty ostatních.

Proč to vadí:
Recepce ověřila, že člověk bydlí v hotelu, ale nezkontrolovala číslo pokoje.

Jak to opravit:
1. Přidat do serverového dotazu filtr podle ID přihlášeného uživatele nebo organizace.
2. Stejnou kontrolu použít pro čtení, změnu i smazání.

Riziko opravy a rollback:
Střední; může odhalit legitimní sdílení, které dosud nebylo výslovně modelované. Před změnou sepsat očekávanou matici přístupů.

Jak ověřit opravu:
Účet A zopakuje request na projekt B. Očekávaný výsledek je 403 nebo 404 bez dat. Vlastní projekt A musí zůstat dostupný.

Do budoucna si pamatuj:
Přihlášení potvrzuje totožnost; oprávnění k jednomu konkrétnímu záznamu se kontroluje zvlášť.
```
