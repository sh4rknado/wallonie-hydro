# Wallonie Hydro — intégration Home Assistant

Intégration Home Assistant pour surveiller la **hauteur d'eau** et le **débit** des cours d'eau de Wallonie (Belgique), à partir des données officielles du portail **[hydrometrie.wallonie.be](https://hydrometrie.wallonie.be)** (SPW — Service public de Wallonie, service Kisters KIWIS).

Conçue et testée avec la station **Givry (L6710) sur la Trouille**, elle fonctionne avec les **320 stations de hauteur** et **287 stations de débit** du réseau wallon (Meuse, Sambre, Semois, Ourthe, Lesse, Trouille, etc.).

[![Ajouter ce dépôt à HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=sh4rknado&repository=wallonie-hydro&category=integration)

> **Note** : le bouton fonctionne avec « My Home Assistant » (service officiel). Si la redirection ne s'ouvre pas depuis votre installation, utilisez l'option B ci-dessous — le résultat est identique.

## Fonctionnalités

- 🌊 **Capteur hauteur d'eau** (m) — série temps réel 10 min, identique à la valeur affichée sur le portail
- 💧 **Capteur débit** (m³/s) quand la station le mesure
- 📈 **Tendances hauteur/débit** calculées par le SPW (m/h, m³/s/h) + variation 1 h / 24 h
- 🚨 **Capteurs binaires d'alerte** à 3 seuils configurables (vigilance / alerte / crue)
- 🕐 **Historique 48 h** conservé par l'intégration (attributs + service WebSocket)
- 📊 **Carte Lovelace** `wallonie-hydro-card` : courbe 48 h hauteur + débit, seuils colorés, flèche de tendance
- 🗺️ Installation via **HACS** (dépôt personnalisé) ou copie manuelle
- 🌐 Traductions **français / anglais / néerlandais**
- Aucune clé API — le service KIWIS du SPW est public

## Installation

### HACS (recommandé)

**Option A — en un clic (bouton « Add to Home Assistant »)**

1. Cliquez sur le bouton bleu en haut de ce README : ![hacs_repository](https://my.home-assistant.io/badges/hacs_repository.svg)
2. Confirmez l'ouverture de `my.home-assistant.io` : la page « Ajouter un dépôt » s'ouvre avec l'URL et la catégorie **Intégration** déjà pré-remplies.
3. Cliquez sur **Soumettre**, puis suivez les étapes 2-4 de l'option B.

> Le bouton nécessite que « My Home Assistant » soit actif sur votre instance
> (le lien redirige automatiquement). S'il ne fonctionne pas, utilisez l'option B.

**Option B — dépôt personnalisé (manuel)**

1. Dans Home Assistant : `HACS → ⋮ (en haut à droite) → Dépôts personnalisés`
2. Renseignez :
   - **URL du dépôt** : `https://github.com/sh4rknado/wallonie-hydro` *(l'URL de ce dépôt GitHub)*
   - **Type / Catégorie** : **Intégration**
3. Cliquez sur **Ajouter** — « Wallonie Hydro » apparaît dans la liste des intégrations HACS.
4. `HACS → Intégrations → Wallonie Hydro → Télécharger`, puis choisissez la version **1.0.0**.
5. **Redémarrez Home Assistant** (Paramètres → Système → Alimentation → Redémarrer).

### Manuel (sans HACS)

1. Copiez le dossier `custom_components/wallonie_hydro/` de ce dépôt dans le dossier `config/custom_components/` de votre installation :

   ```
   config/
   └── custom_components/
       └── wallonie_hydro/
           ├── __init__.py
           ├── api.py
           ├── manifest.json
           ├── ...
           └── www/wallonie-hydro-card.js
   ```

2. Pour la carte Lovelace, copiez aussi `www/wallonie-hydro-card.js` dans `config/www/wallonie_hydro/` (voir la section « Carte Lovelace »).
3. Redémarrez Home Assistant.

## Configuration

1. `Paramètres → Appareils et services → Ajouter une intégration`
2. Recherchez **Wallonie Hydro**
3. Indiquez le **numéro de station** — pour Givry sur la Trouille : **`L6710`**

> Pour trouver le numéro d'une autre station : ouvrez
> [la carte du portail](https://hydrometrie.wallonie.be/home/observations/hauteur.html?mode=map),
> cliquez sur la station, le numéro apparaît dans l'URL (`station=DCENN/L6710`).
> Vous pouvez aussi essayer directement le nom : tapez le numéro affiché sur la carte.

Chaque station ajoutée crée un appareil avec ses capteurs :

| Entité | Description |
|---|---|
| `sensor.<station>_hauteur_d_eau` | Hauteur d'eau (m), pas 10 min |
| `sensor.<station>_debit` | Débit (m³/s), si mesuré |
| `sensor.<station>_tendance_hauteur` | Tendance SPW (m/h) |
| `sensor.<station>_tendance_debit` | Tendance SPW (m³/s/h) |
| `binary_sensor.<station>_vigilance` | ON si hauteur ≥ seuil vigilance |
| `binary_sensor.<station>_alerte` | ON si hauteur ≥ seuil alerte |
| `binary_sensor.<station>_crue` | ON si hauteur ≥ seuil crue |

### Options (seuils et fréquence)

`Appareils → Wallonie Hydro (station) → Configurer` :

- **Intervalle de mise à jour** : 1 à 120 min (défaut 10 min)
- **Seuil de vigilance / alerte / crue** (m) — défauts 1,0 / 1,5 / 2,0 ; à adapter à votre station (la Trouille à Givry évolue typiquement entre 0,3 et 1 m ; lors des crues de référence, elle dépasse 2 m)

## Carte Lovelace

La carte est fournie avec l'intégration. Déclarez-la comme ressource
(`Paramètres → Tableaux de bord → ⋮ → Ressources`) :

```yaml
url: /wallonie_hydro/wallonie-hydro-card.js
type: module
```

> Avec l'installation HACS, la ressource est ajoutée automatiquement si vous
> activez « Lovelace » dans les paramètres du dépôt HACS. L'URL
> `/local/wallonie_hydro/wallonie-hydro-card.js` fonctionne aussi si vous
> copiez le fichier `www/wallonie-hydro-card.js` dans votre dossier `config/www/wallonie_hydro/`.

Puis dans un tableau de bord (mode YAML) :

```yaml
type: custom:wallonie-hydro-card
station: L6710
name: Trouille à Givry
hours: 48
show_discharge: true
thresholds:
  warn: 0.8
  alert: 1.2
  high: 1.8
```

| Option | Défaut | Description |
|---|---|---|
| `station` | — | Numéro de station (obligatoire, ex. `L6710`) |
| `name` | nom de la station | Titre de la carte |
| `hours` | 48 | Fenêtre d'affichage (max 48 h) |
| `show_discharge` | `true` | Superpose la courbe de débit (axe droit implicite) |
| `thresholds.warn/alert/high` | — | Seuils (m) tracés en pointillés colorés |
| `height_entity` | auto | Entité hauteur à utiliser pour la valeur affichée |

La carte récupère l'historique via le service WebSocket de l'intégration
(`wallonie_hydro/history`) : pas de requête externe depuis le navigateur,
pas de clé, et les données restent en cache côté Home Assistant.

## Automatisations

### Notification quand le niveau franchit le seuil d'alerte

```yaml
alias: Trouille - franchissement seuil d'alerte
description: Notifie quand la hauteur de la Trouille à Givry dépasse le seuil.
trigger:
  - platform: numeric_state
    entity_id: sensor.givry_hauteur_d_eau
    above: 1.2
condition:
  - condition: time
    after: "06:00:00"
    before: "23:00:00"
action:
  - service: notify.mobile_app_mon_telephone
    data:
      title: "🌊 Trouille en hausse"
      message: >
        Hauteur : {{ states('sensor.givry_hauteur_d_eau') }} m à Givry
        ({{ state_attr('sensor.givry_hauteur_d_eau', 'change_1h_value') | float(0) | round(2) }} m sur 1 h).
      data:
        link: https://hydrometrie.wallonie.be/home/observations/hauteur.html?mode=graph&station=DCENN%2FL6710&topic=H-hr
mode: single
```

### Synthèse matinale

```yaml
alias: Synthèse hydro matinale
trigger:
  - platform: time
    at: "07:30:00"
action:
  - service: notify.mobile_app_mon_telephone
    data:
      title: "🌊 Point hydro du jour"
      message: >
        Trouille à Givry : {{ states('sensor.givry_hauteur_d_eau') }} m,
        débit {{ states('sensor.givry_debit') }} m³/s,
        tendance {{ states('sensor.givry_tendance_hauteur') }} m/h.
mode: single
```

## Comment ça marche

L'intégration interroge le même service que le portail public :
`https://hydrometrie.wallonie.be/services/KiWIS/KiWIS` (API Kisters KIWIS,
`request=GetStationList / GetTimeseriesList / GetTimeseriesValues`).
Elle utilise les **séries officielles** affichées sur la carte du portail :
`<direction>/<station>/H/Cmd.Rel.Abs.Comp-Alarmes` (hauteur) et
`<direction>/<station>/Q/Cmd.RunOff.Comp-Alarmes` (débit), rafraîchies toutes
les 10 minutes.

## Stations sur la Trouille

| Station | Commune | Numéro |
|---|---|---|
| Givry | Givry | **L6710** |
| Harmignies | Harmignies | L6430 |
| Spiennes | Spiennes | L6600 |
| Cuesmes | Cuesmes | 3642 (sans H) |
| Hyon | Hyon | 3643 (sans H) |

## Dépannage

- **« Station introuvable »** : vérifiez le numéro dans l'URL du portail après avoir cliqué la station sur la carte.
- **« Pas de série H/Q »** : certaines stations sont pluviométriques ou inactives (ex. 3642 Cuesmes). Choisissez une station avec un graphe de hauteur sur le portail.
- **Valeur différente du portail** : le portail affiche parfois la hauteur absolue (`Habs`) selon la station ; cette intégration suit la série relative officielle du topic `H-hr`, identique à la courbe du portail.
- **Carte «Erreur : station_not_found»** : la carte lit l'historique via l'intégration ; ajoutez d'abord la station dans l'intégration (`station: L6710` doit correspondre).

## Licence

MIT — les données restent la propriété du SPW Wallonie (portail hydrometrie.wallonie.be).
