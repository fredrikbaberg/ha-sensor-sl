SL sensor for Home Assistant
========================

**This is a fork of fuffenz SL sensor (https://github.com/fuffenz/ha-sensor-sl).**

This is a simple component for Home Assistant that can be used to create a "Departure board" for buses and trains in Stockholm, Sweden.  You have to install it as a custom component and you need to get your own API key from SL / Trafiklab.

- First, visit [https://www.trafiklab.se/api](https://www.trafiklab.se/api) and create a free account. They provide multiple APIs, the one you want is ["SL Trafikinformation 4"](https://www.trafiklab.se/api/sl-realtidsinformation-4).  
When you have your API key, you're ready to add the component to your Home Assistant. Since this is a custom component, you need to add it manually to your config directory.

- Create a folder named **custom_components** under your Home Assistant **config** folder. 

- Create a folder named **sensor** under the **custom_components** folder.

- Download sl.py from here and put it in the **sensor** folder.

- Edit your configuration.yaml file and add the component

```yaml
# Example configuration.yaml entry
- platform: sl
  name: gullmarsplan
  ri4key: YOUR-API-KEY-HERE
  siteid: 9189
  timewindow: 60
  sensor: binary_sensor.test
  departures:
    - sensorname: sensor_name
      lines: 17, 18, 19
      direction: 1
```


**Configuration variables**


- name: The name of the sensor (will be prefixed with "sl_") 

- ri4key: Your API key from Trafiklab

- siteid: The ID of the bus stop or station you want to monitor.  You can find the ID with some help from another API, **sl-platsuppslag**.  In the example above, site 9189 is Gullmarsplan.

- timewindow (optional): Time window for departures, number of minutes from now. Maximum (default) is 60 minutes.

- sensor: (optional) Sensor to determine if status should be updated. If sensor is 'on', or if this option is not set, update will be done.

- departures (optional): Add details to departures here, for instance separated by different lines.

  - sensorname: (optional) Name of sensor to use to enable/disable calling sensor. Should be input_boolean or similar (using 'on'/'off' state). If 'off', all data will be cleared and API should not be called.

  - lines: (optional) A comma separated list of line numbers that you are interested in. Most likely, you only want info on the bus that you usually ride.  If omitted, all lines at the specified site id will be included.  In the example above, lines 17, 18 and 19 will be included.

  - direction: (optional) Unless your site id happens to be the end of the line, buses and trains goes in both directions.  You can enter **1** or **2**.  If omitted, both directions are included.

**sensor value**

The sensor value is the number of departures, attributes are details for each departure according to:
```
"attribution": "Data from sl.se / trafiklab.se",
"unit_of_measurement": "departures",
"friendly_name": "sl sensorname_raw",
"icon": "fa-subway"
"departures": [
  "line": "163",
  "departure": "Nu",
  "destination": "Kärrtorp",
  "time": 0,
  "deviations": ""
]
```

<!-- The sensor value is the number of minutes to the next departure.  There are also a number of attributes:

```
next_departure: 1 min
next_line: 17
next_destination: Åkeshov
upcoming_departure: 4 min
upcoming_line: 18
upcoming_destination: Hässelby strand
unit_of_measurement: min
icon: fa-subway
friendly_name: sl gullmarsplan
attribution: Data from sl.se / trafiklab.se
``` -->

**API-call restrictions**

The `Bronze` level API is limited to 30 API calls per minute, 10.000 per month.
For a private project, `Silver` level does not seem possible.
With 10.000 calls per month, that allows for less than one call every 4 minute.


**custom_updater**

For update check of this sensor, add the following to your configuration.yaml. For more information, see [[custom_updater](https://github.com/custom-components/custom_updater/wiki/Installation)]

```
custom_updater:
  component_urls:
    - https://raw.githubusercontent.com/fredrikbaberg/ha-sensor-sl/dev/custom_updater.json
  card_urls:
    - https://raw.githubusercontent.com/fredrikbaberg/ha-sensor-sl/dev/custom_cards.json
```

**Lovelace card**

To display data using Lovelace, you can try the included card (*NOT* updated to work with multi-departure changes!).

Present departure times from custom component SL-sensor in a card. Can use multiple sensors, will show next and upcoming departure for each sensor.

![sl-example](https://user-images.githubusercontent.com/19709460/46255050-d4427b80-c498-11e8-9d30-2510e803e02b.png)

Install it throgh copying the file `www/sl-card.js` into `config_dir/www/`, and use the following in your ui-lovelace.yaml file:
```
resources:
  - url: /local/sl-card.js
    type: js
```
and use the card throgh
```
cards:
  - type: "custom:sl-card"
    entities:
      - sensor.sl_name
```
