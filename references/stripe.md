# Stripe a platební integrace

Načti tento modul, když projekt přijímá platby, předplatné, refundace nebo jiné finanční operace. Příklady jsou psané pro Stripe; u jiné služby použij stejné principy a ověř její oficiální dokumentaci.

## Obsah

1. Klíče a prostředí
2. Sběr platebních údajů
3. Cena a obchodní logika
4. Checkout a návratové URL
5. Webhooky
6. Idempotence, souběh a stavové změny
7. Předplatné, refundace a oprávnění
8. Metadata, logy a soukromí
9. Účty, přístupy a provoz
10. Povinné testy
11. Oficiální zdroje

## 1. Klíče a prostředí

### Rozlišuj typy

- Publishable key (`pk_...`) je určený pro klienta.
- Secret key (`sk_...`) patří pouze na server.
- Restricted key má omezený scope a je vhodnější pro komponentu, která nepotřebuje plná práva.
- Webhook signing secret (`whsec_...`) je samostatné tajemství pro konkrétní endpoint.

Testovací secret je stále secret. Nesmí být v klientském bundle, veřejném repozitáři, URL, logu ani screenshotu.

### Ověř

- test a live klíče jsou oddělené;
- preview nepoužívá live secret ani live webhook endpoint;
- každý backend používá nejmenší potřebné oprávnění;
- staré a nepoužívané klíče jsou odstraněné nebo rotované;
- klíče nejsou sdílené v chatu, e-mailu ani dokumentaci;
- při úniku se postupuje podle `incident-response.md`;
- report obsahuje pouze typ a maskovaný konec, nikdy hodnotu.

## 2. Sběr platebních údajů

- Preferuj Stripe Checkout, Payment Element nebo oficiální klientské komponenty před vlastním sběrem čísla karty.
- Číslo karty, CVC a jiné citlivé platební údaje neposílej přes vlastní server, logy nebo analytiku, pokud k tomu projekt nemá odborně navržený a odpovídající compliance režim.
- Neuchovávej raw platební údaje v databázi.
- Ověř HTTPS a správnou doménu.
- Zkontroluj, zda testovací formulář nemůže omylem vytvořit live platbu.

Pokud projekt přímo zpracovává platební údaje nebo používá nestandardní flow, doporuč odbornou revizi.

## 3. Cena a obchodní logika

Klient nesmí být autoritativním zdrojem ceny, slevy ani stavu zaplaceno.

### Ověř server

- Klient posílá bezpečný identifikátor produktu nebo price ID, ne libovolnou částku.
- Server načte cenu z důvěryhodné konfigurace, databáze nebo Stripe.
- Server ověří měnu, množství, slevu, daň a oprávnění uživatele.
- Uživatel nemůže změnit product/price ID na produkt, který nemá být dostupný.
- Slevový kód má omezení použití, uživatele, produktu a času podle záměru.
- Stav objednávky se mění transakčně a nelze přeskočit potřebný krok.
- Bezplatná nebo záporná částka nevznikne nečekanou kombinací hodnot.
- Server nevěří `paid=true`, `isPremium=true`, `role` nebo podobnému poli z prohlížeče.

### Testy manipulace

Zachyť testovací request a bezpečně změň:

- cenu;
- množství;
- měnu;
- product/price ID;
- slevu;
- ID uživatele nebo objednávky.

Server musí změnu odmítnout nebo přepočítat z důvěryhodných dat.

## 4. Checkout a návratové URL

Success URL je pouze navigace uživatele, ne důkaz platby.

- Nepřiděluj přístup jen proto, že uživatel otevřel `/success`.
- Ověř skutečný PaymentIntent, Checkout Session, invoice, subscription nebo entitlement na serveru.
- Preferuj webhook pro asynchronní potvrzení a serverový dotaz pro zobrazení aktuálního stavu.
- `success_url`, `cancel_url` a `return_url` omez na vlastní důvěryhodné domény.
- Session ID v URL nepovažuj za secret, ale stále ověř vazbu na správného uživatele.
- Uživatel nesmí načíst cizí Checkout Session nebo objednávku změnou ID.

## 5. Webhooky

### Podpis

- Ověř podpis pomocí oficiálního Stripe SDK.
- Použij nezměněné raw request body. JSON parser před ověřením může podpis zneplatnit.
- Použij signing secret odpovídající přesně danému endpointu a prostředí.
- Odmítnutý podpis vrať jako chybu a neprováděj žádnou obchodní operaci.
- Nevypisuj payload ani signing secret do veřejného logu.

### Kontext události

- Ověř live/test mode a očekávaný účet, případně connected account.
- Zpracovávej jen potřebné event types.
- Nevěř metadata bez vazby na vlastní serverový záznam.
- Podle potřeby načti aktuální objekt přes API, protože události mohou přijít mimo pořadí.

### Duplicity a pořadí

Stripe může událost doručit opakovaně a nezaručuje pořadí všech událostí.

- Ulož zpracované `event.id` nebo jiný jedinečný klíč.
- Stejná událost nesmí dvakrát přidělit přístup, vytvořit fakturu, odeslat zboží nebo refundovat.
- Handler musí zvládnout, že `invoice.paid` přijde před jinou očekávanou událostí.
- Stav odvozuj z aktuálních důvěryhodných dat, ne pouze z pořadí callbacků.

### Dostupnost

- Vrať rychle `2xx` až po bezpečném přijetí nebo idempotentním zapsání práce.
- Dlouhé zpracování přesuň do fronty, je-li potřeba.
- Retry musí být bezpečný.
- Loguj ID události, typ a výsledek bez citlivého payloadu.
- Sleduj failed/pending deliveries a určuj vlastníka reakce.

## 6. Idempotence, souběh a stavové změny

Idempotence znamená, že bezpečné opakování stejné operace nevytvoří druhý nežádoucí efekt.

- U vytváření nebo změny objektu přes Stripe API použij idempotency key podle aktuálního API a SDK.
- Klíč vázej na jednu konkrétní obchodní operaci, ne na všechny požadavky uživatele.
- V databázi použij unikátní omezení pro Stripe object ID, event ID nebo order ID.
- Ověř souběžné kliknutí, reload, retry po timeoutu a dvojí webhook.
- Stavový automat nesmí přejít z refundováno zpět na zaplaceno nebo zrušeno na aktivní bez explicitního povoleného přechodu.
- Částečné selhání musí mít retry nebo kompenzační krok; neoznačuj objednávku za zaplacenou dřív, než je důkaz uložen.

## 7. Předplatné, refundace a oprávnění

### Předplatné

- Přístup určuj z aktuálního stavu subscription/entitlement a vlastních pravidel, ne pouze z poslední success stránky.
- Ošetři trial, past_due, unpaid, canceled, pause, změnu plánu a konec období.
- Změna ceny nebo plánu musí patřit správnému customerovi a uživateli.
- Customer Portal URL vydávej až po autentizaci a ověření vlastnictví customer ID.

### Refundace a administrace

- Refundaci smí provést pouze oprávněná role.
- Částku, payment ID a důvod ověř na serveru.
- Opakovaná refundace musí být idempotentní a odpovídat aktuálnímu stavu.
- Administrátorská finanční operace má audit log a podle rizika potvrzení nebo oddělení rolí.
- Nikdy nevystavuj univerzální endpoint s libovolnou Stripe metodou.

## 8. Metadata, logy a soukromí

- Do Stripe metadata ukládej minimum potřebných identifikátorů.
- Nevkládej hesla, tokeny, zdravotní údaje nebo zbytečné osobní informace.
- Metadata z klienta před uložením validuj a neber je jako autoritativní.
- Logy nesmějí obsahovat secret key, `whsec`, Authorization header ani celé osobní payloady.
- Veřejný error nesmí vracet interní Stripe error objekt s citlivými detaily.
- Uživatel smí vidět pouze své platby, invoices a subscription data.
- Retenci dat a exporty řeš podle obchodních a právních požadavků projektu.

## 9. Účty, přístupy a provoz

- Stripe účet má 2FA/passkey a bezpečnou obnovu.
- Členové týmu mají nejmenší potřebnou roli.
- Staré členy, aplikace a restricted keys odeber.
- Webhook endpointy, destinations a API versions jsou zdokumentované.
- Test a live prostředí mají vlastní produkty, ceny, webhooks a alerty.
- Sleduj neobvyklé platby, refundace, disputes a failed webhooks.
- Ověř postup pro rotaci klíče bez výpadku.
- Ověř rollback aplikace tak, aby stará verze nepoužila již zneplatněný klíč nebo nekompatibilní webhook schema.

## 10. Povinné testy

V test mode bezpečně ověř:

1. Změna ceny v klientském requestu neovlivní autoritativní částku.
2. Otevření success URL bez platby nepřidělí produkt.
3. Chybějící nebo špatný webhook podpis nic nezmění.
4. Stejný webhook dvakrát nevytvoří dvojí efekt.
5. Události mimo pořadí neporuší stav.
6. Účet A nemůže získat invoice, session, portal ani subscription účtu B.
7. Testovací flow nepoužívá live key, live product ani produkční webhook secret.
8. Refundaci nebo změnu plánu nelze provést bez oprávnění.
9. Timeout a retry Stripe API nevytvoří dvojí operaci.
10. Logy a chyby neobsahují tajné hodnoty.

## 11. Oficiální zdroje

Ověř v den auditu:

- API keys: https://docs.stripe.com/keys
- Webhooks: https://docs.stripe.com/webhooks
- Signature verification: https://docs.stripe.com/webhooks/signature
- Idempotent requests: https://docs.stripe.com/api/idempotent_requests
- Checkout fulfillment: https://docs.stripe.com/checkout/fulfillment
- Security: https://docs.stripe.com/security

Do reportu uveď test/live prostředí, ověřené endpointy, API/SDK verzi a datum dokumentace. Pokud nemáš dashboard nebo testovací účet, platební nastavení označ jako `NEOVĚŘENO` a nevydávej zelený release verdict.
