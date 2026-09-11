# Bodyguard

Claude skill pro srozumitelné, důkazně podložené bezpečnostní audity webů a aplikací vytvořených pomocí AI nebo vibe codingu.

Bodyguard je určený hlavně pro lidi, kteří nejsou vývojáři/vývojářky, ale postavili si vlastní web nebo appku pomocí AI a chtějí vědět, jestli je bezpečné ji zveřejnit. Vysvětluje vše srozumitelnou češtinou, odděluje kontrolu kódu, služeb a živého nasazení, nikdy do reportu nevypíše celý nalezený klíč nebo heslo (jen typ a pár posledních znaků) a nikdy nevydává falešnou zelenou k nasazení bez důkazu.

Víc o tom, jak a proč skill vznikl, najdeš v článku na [jaknaai.cz](https://jaknaai.cz/clanky/bodyguard).

## Co skill umí

- Kontroluje repozitář, složku projektu, nasazenou URL i související služby (GitHub, Supabase, Stripe, Vercel...).
- Podporuje víc režimů: `quick` (před commitem), `release`/`launch` (před nasazením), `full` (podrobný audit), `services`, `verify` (ověření opravy), `incident` (reakce na únik) a `fix`.
- Používá bezpečné read-only skripty, které v reportu nikdy neukážou celou nalezenou hodnotu klíče nebo hesla — jen typ, umístění a pár posledních znaků.
- Řídí se přísnými pravidly: bez souhlasu nic nenasazuje, nemaže, nerotuje klíče ani nespouští neznámý kód.
- Vždy odděluje ověřené nálezy od podezření a neověřených oblastí — nikdy neřekne jen "je to bezpečné".

## Instalace

1. Stáhni celý obsah tohoto repozitáře (nebo ho naklonuj: `git clone https://github.com/eliskavyhnankova/bodyguard-skill.git`).
2. Zkopíruj celou složku do adresáře, kde Claude hledá skilly (podle toho, jestli používáš Claude Code, Claude Desktop nebo jiné rozhraní — postup se může lišit).
3. Skill se jmenuje `bodyguard` podle názvu ve `SKILL.md`.

## Jak ho použít

Stačí Claudovi napsat něco jako:

> Zkontroluj mi bezpečnost projektu před nasazením.

nebo rovnou zadat konkrétní režim, například:

> Udělej quick kontrolu před commitem.
> Bodyguard full audit.
> Bodyguard incident — myslím, že mi unikl API klíč.

## Struktura

```
SKILL.md                     hlavní instrukce a pracovní postup
agents/openai.yaml           metadata pro zobrazení skillu
references/                  detailní kontrolní moduly (auth, Supabase, Stripe, AI apps, uploady...)
scripts/                     bezpečné read-only Python skripty (sken tajemství, pasivní kontrola URL, inventura stacku, audit závislostí)
```

## Bezpečnost

Skript neinstaluje nic automaticky, nespouští projektový kód bez souhlasu a v reportu nikdy neukáže celý nalezený klíč nebo heslo — jen typ a pár posledních znaků, podobně jako banka na výpisu ukazuje jen poslední čtyři číslice karty. Detailní pravidla jsou popsaná v `SKILL.md` v sekci "Neměnná bezpečnostní pravidla".

I tak platí: automatická kontrola nenahrazuje cílený penetrační test u vysoce citlivých nebo kritických projektů. Skill sám doporučuje, kdy je čas zavolat odborníka — viz `references/standards-and-escalation.md`.

## Licence

[MIT](LICENSE) — použij, uprav a sdílej dál, jak potřebuješ.
