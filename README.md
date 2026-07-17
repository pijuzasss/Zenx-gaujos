# ZENX gaujų Discord botas (Python)

## Funkcijos

- Žinutė `@narys on` pažymėtam nariui uždeda tą pačią gaujos rolę, kurią turi žinutės autorius (pvz. `// PILKI // GAUJA6`).
- Žinutės `@narys on des` ir `@narys on desine` pažymėtam nariui uždeda autoriaus gaujos ir `.env` faile nurodytą `des.ranka` roles. Jei narys jau turi tą pačią gaują, pridedama tik `des.ranka`.
- Žinutė `@narys off` nuima pažymėto nario tos pačios gaujos rolę, boss ir `des.ranka`. Jei autorius ir pažymėtas narys neturi tos pačios gaujos rolės, nieko nenuima.
- Žinutės autorius privalo turėti rolę, kurios pavadinime yra `gauja`, bet nėra `boss`.
- Kol nariui aktyvi `3d cooldown` rolė, su `@narys on` jo į gaują priimti negalima.
- Jei pažymėtas narys turi `black list` rolę, nei `on`, nei `on des`, nei `on desine` jam nieko neuždeda.
- Jei pažymėtas narys jau turi visiškai kitos gaujos rolę, visos `on` komandos jam nieko neuždeda.
- `/disband gauja:@GaujosRole` visiems tos rolės nariams nuima visas boto valdomas roles (taip pat boss), uždeda `3d cooldown` ir automatiškai ją nuima po 72 valandų.
- `/disban` yra trumpesnis tos pačios komandos variantas. Ji nuima gaujos, boss, `des.ranka` ir visas kitas roles, kurias botas gali valdyti.
- Cooldown terminai išsaugomi diske, todėl veikia ir perkrovus botą.
- Visas `/disband` darbas išsaugomas prieš keičiant roles. Jei botas netikėtai išjungiamas proceso viduryje, paleistas iš naujo jis automatiškai užbaigia likusius narius.
- Kiekvieno nario būsena įrašoma iškart atominiu būdu į `data/state.json`, todėl nereikia kartoti komandos.

## Paleidimas

1. Įsidiek Python 3.10 arba naujesnį.
2. Discord Developer Portal sukurk botą ir įjunk **Server Members Intent** bei **Message Content Intent**.
3. Pakviesk botą su `bot` ir `applications.commands` scope; suteik `Manage Roles`, `View Channels`, `Send Messages`, `Read Message History` teises.
4. Boto rolę serverio rolių sąraše pakelk aukščiau visų rolių, kurias jis turės uždėti ar nuimti.
5. Atidaryk jau sukurtą `.env` ir įrašyk tokeną, application ID bei serverio ID.
6. Paleisk:

```powershell
py -m pip install -r requirements.txt
py bot.py
```

## Rolių pavadinimai

Pavyzdžiui, jei komandos autorius turi rolę `// PILKI // GAUJA6`, parašius `@narys on` pažymėtam nariui bus uždėta būtent `// PILKI // GAUJA6` rolė. `GAUJOS BOSAS` rolė ignoruojama.

Tekstus ir 72 valandų trukmę galima pakeisti `.env` faile.

## Railway talpinimas

1. Įkelk projektą į privatų GitHub repository. `.env` failo nekelk – jis jau įtrauktas į `.gitignore` ir `.dockerignore`.
2. Railway sukurk naują projektą, pasirink `Deploy from GitHub repo` ir prijunk repository.
3. Service skiltyje `Variables` pridėk: `DISCORD_TOKEN`, `CLIENT_ID`, `GUILD_ID`, `GANG_ROLE_TEXT`, `BOSS_ROLE_TEXT`, `RIGHT_HAND_ROLE_TEXT`, `BLACKLIST_ROLE_TEXT`, `COOLDOWN_ROLE_NAME`, `COOLDOWN_HOURS`.
4. Prie boto service pridėk Railway Volume ir nustatyk jo mount path į `/data`. Railway automatiškai perduos `RAILWAY_VOLUME_MOUNT_PATH`, todėl botas ten laikys `state.json`.
5. Palik vieną replica. Keli vienu metu veikiantys to paties Discord boto egzemplioriai konfliktuotų dėl komandų ir būsenos.
6. Railway automatiškai aptiks `Dockerfile`, įdiegs Python bibliotekas ir paleis `bot.py`.

Viešo domeno ar porto šiam Discord botui nereikia. Deploy loguose sėkmę rodo eilutė `Prisijungta kaip ...`.

> Svarbu: `/disband` tyčia nuima visas roles, kurias botas gali valdyti, ne tik gaujos roles. Discord integracijų valdomų ir už botą aukštesnių rolių nuimti neleidžia pati Discord platforma.
