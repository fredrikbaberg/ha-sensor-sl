"""Simple service for SL (Storstockholms Lokaltrafik)"""
import datetime
import logging
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.util import Throttle
from homeassistant.util import dt as dt_util
from homeassistant.helpers.entity import Entity

__version__ = '0.0.4'

REQUIREMENTS = ['requests']

_LOGGER = logging.getLogger(__name__)

CONF_RI4_KEY = 'ri4key'
CONF_SITEID = 'siteid'
CONF_DEPARTURES = 'departures'
CONF_NAME = 'name'
CONF_LINES = 'lines'
CONF_DIRECTION = 'direction'
CONF_ENABLED_SENSOR = 'sensor'

MIN_UPDATE_FREQUENCY = timedelta(seconds=60)

USER_AGENT = "Home Assistant SL Sensor"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_RI4_KEY): cv.string,
    vol.Required(CONF_SITEID): cv.string,
    vol.Optional(CONF_DEPARTURES): [{
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_LINES): cv.string,
        vol.Optional(CONF_DIRECTION): cv.string,
        vol.Optional(CONF_ENABLED_SENSOR): cv.string
    }]
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Setup the sensors."""

    sensors = []
    # Raw data sensor, get data from API and use this data for "sub-sensors".
    sensors.append(
        SLDepartureBoardSensor(
            hass,
            SlDepartureBoardData(
                config.get(CONF_RI4_KEY),
                config.get(CONF_SITEID)
            ),
            config,
            config.get(CONF_NAME)+'_raw' or config.get(CONF_SITEID)+'_raw'
        )
    )
    add_entities(sensors)


class SLDepartureBoardSensor(Entity):
    """Departure board for one SL site."""

    def __init__(self, hass, data, config, name):
        """Initialize"""
        self._hass = hass
        self._sensor = 'sl'
        self._name = name
        self._data = data
        self._board = []
        self._error_logged = False  # Keep track of if error has been logged.
        self._enabled_sensor = config.get(CONF_ENABLED_SENSOR)

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}_raw'.format(self._sensor, self._name)

    @property
    def icon(self):
        """ Return the icon for the frontend."""
        return 'fa-subway'

    @property
    def state(self):
        """ Return number of minutes to the next departure """
        if len(self._board) > 0:
            return self._board[0]['time']

        return 9999

    @property
    def device_state_attributes(self):
        """ Return the sensor attributes ."""

        val = {}
        val['attribution'] = 'Data from sl.se / trafiklab.se'
        val['unit_of_measurement'] = 'departures'

        val['departures'] = len(self._board)

        for departure_nr in range(0, len(self._board)):
            val['line_{}'.format(departure_nr)] = \
                self._board[departure_nr]['line']
            val['destination_{}'.format(departure_nr)] = \
                self._board[departure_nr]['destination']
            val['departure_{}'.format(departure_nr)] = \
                self._board[departure_nr]['departure']

        return val

    def parseDepartureTime(self, t):
        """Weird time formats from the API,
        do some quick and dirty conversions
        """
        try:
            if t == 'Nu':
                return 0
            s = t.split()
            if(len(s) > 1 and s[1] == 'min'):
                return int(s[0])
            s = t.split(':')
            if(len(s) > 1):
                now = datetime.datetime.now()
                min = (int(s[0])*60 + int(s[1])) - (now.hour*60 + now.minute)
                if min < 0:
                    min = min + 1440
                return min
        except Exception:
            _LOGGER.error('Failed to parse departure time (%s) ', t)
        return 0

    def update(self):
        """Get the departure board."""
        if self._enabled_sensor is not None:
            sensor_state = self._hass.states.get(self._enabled_sensor)
        if self._enabled_sensor is None or sensor_state.state is STATE_ON:
            self._data.update()
            board = []
            if self._data.data['StatusCode'] != 0:
                if not self._error_logged:
                    _LOGGER.warn("Status code: {}, {}".format(
                        self._data.data['StatusCode'],
                        self._data.data['Message']
                    ))
                    self._error_logged = True  # Report once, until success.
            else:
                if self._error_logged:
                    _LOGGER.warn("API call successful again")
                    self._error_logged = False  # Reset that error has been reported.
                for i, traffictype in enumerate(['Metros', 'Buses', 'Trains', 'Trams', 'Ships']):
                    for idx, value in enumerate(self._data.data['ResponseData'][traffictype]):
                        linenumber = value['LineNumber'] or ''
                        destination = value['Destination'] or ''
                        direction = value['JourneyDirection'] or 0
                        displaytime = value['DisplayTime'] or ''
                        deviations = value['Deviations'] or ''
                        _LOGGER.warn("linenumber: {}, destination: {}, direction: {}, displaytime: {}, deviations: {}".format(
                            linenumber, destination, direction, displaytime, deviations
                        ))
                        if (int(self._data._direction) == 0 or int(direction) == int(self._data._direction)):
                            if(self._data._lines is None or (linenumber in self._data._lines)):
                                diff = self.parseDepartureTime(displaytime)
                                board.append({
                                    "line": linenumber,
                                    "departure": displaytime,
                                    "destination": destination,
                                    'time': diff,
                                    'deviations': deviations
                                })
            self._board = sorted(board, key=lambda k: k['time'])
            _LOGGER.info(self._board)


class SlDepartureBoardData(object):
    """ Class for retrieving API data """

    def __init__(self, apikey, siteid):
        """Initialize the data object."""
        self._apikey = apikey
        self._siteid = siteid
        self.data = {}

    @Throttle(MIN_UPDATE_FREQUENCY)
    def update(self, **kwargs):
        """Get the latest data for this site from the API."""
        import requests

        try:
            _LOGGER.info("fetching SL Data for '%s'", self._siteid)
            url = "{}{}{}{}".format(
                "https://api.sl.se/api2/realtimedeparturesV4.json?key=",
                self._apikey,
                "&siteid=",
                self._siteid
            )
            req = requests.get(
                url,
                headers={"User-agent": USER_AGENT},
                allow_redirects=True,
                timeout=5
            )
        except requests.exceptions.RequestException:
            _LOGGER.error("failed fetching SL Data for '%s'", self._siteid)
            return
        if req.status_code == 200:
            self.data = req.json()
        else:
            _LOGGER.error("{}'{}'({}{})".format(
                "failed fetching SL Data for ",
                self._siteid,
                "HTTP Status_code = ",
                req.status_code
            ))
