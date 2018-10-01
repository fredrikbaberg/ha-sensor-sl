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
# from homeassistant.helpers.event import track_state_change

__version__ = '0.0.5'

REQUIREMENTS = ['requests']

_LOGGER = logging.getLogger(__name__)

CONF_RI4_KEY = 'ri4key'
CONF_SITEID = 'siteid'
CONF_NAME = 'name'
CONF_TIME_WINDOW = 'timewindow'
CONF_ENABLED_SENSOR = 'sensor'
CONF_DEPARTURES = 'departures'
CONF_SENSOR_NAME = 'sensorname'
CONF_LINES = 'lines'
CONF_DIRECTION = 'direction'

DOMAIN = 'sl'

MIN_UPDATE_FREQUENCY = timedelta(seconds=60)

USER_AGENT = "Home Assistant SL Sensor"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_RI4_KEY): cv.string,
    vol.Required(CONF_SITEID): cv.string,
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_TIME_WINDOW, default=60): int,
    vol.Optional(CONF_ENABLED_SENSOR): cv.string,
    vol.Optional(CONF_DEPARTURES): [{
        vol.Optional(CONF_SENSOR_NAME): cv.string,
        vol.Optional(CONF_LINES): cv.string,
        vol.Optional(CONF_DIRECTION): cv.string
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
                config.get(CONF_SITEID),
                config.get(CONF_TIME_WINDOW)
            ),
            config,
            config.get(CONF_NAME) or config.get(CONF_SITEID)
        )
    )
    add_entities(sensors, True)


class SLDepartureBoardSensor(Entity):
    """Departure board for one SL site."""

    def __init__(self, hass, data, config, name):
        """Initialize"""
        self._hass = hass
        self._sensor = 'sl'
        self._name = name+'_raw'
        self._data = data
        self._board = []
        self._error_logged = False  # Keep track of if error has been logged.
        self._enabled_sensor = config.get(CONF_ENABLED_SENSOR)
        self._departures = [[], []]
        for departure in config.get(CONF_DEPARTURES):
            lines = departure.get(CONF_LINES)
            if lines is not None:
                for line in lines:
                    self._departures[0].append(line)
            self._departures[1].append(departure.get(CONF_DIRECTION))

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self._sensor, self._name)

    @property
    def icon(self):
        """ Return the icon for the frontend."""
        return 'fa-subway'

    @property
    def state(self):
        """ Return number of departures on board. """
        return len(self._board)

    @property
    def device_state_attributes(self):
        """ Return the sensor attributes. """

        val = {}
        val['attribution'] = 'Data from sl.se / trafiklab.se'
        val['unit_of_measurement'] = 'departures'

        val['departures'] = len(self._board)
        val['departures'] = [board for board in self._board]

        # for departure_nr in range(0, len(self._board)):
        #     val['line_{}'.format(departure_nr)] = \
        #         self._board[departure_nr]['line']
        #     val['destination_{}'.format(departure_nr)] = \
        #         self._board[departure_nr]['destination']
        #     val['departure_{}'.format(departure_nr)] = \
        #         self._board[departure_nr]['departure']

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
        sensor_state = None
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
                    self._error_logged = False  # Reset error reported.
                for i, traffictype in enumerate(
                    ['Metros', 'Buses', 'Trains', 'Trams', 'Ships']
                ):
                    for idx, value in enumerate(
                        self._data.data['ResponseData'][traffictype]
                    ):
                        linenumber = value['LineNumber'] or ''
                        destination = value['Destination'] or ''
                        direction = value['JourneyDirection'] or 0
                        displaytime = value['DisplayTime'] or ''
                        deviations = value['Deviations'] or ''
                        if None in self._departures[1] or \
                                int(direction) in self._departures[1]:
                            if not self._departures[0] or \
                                    linenumber in self._departures[0]:
                                diff = self.parseDepartureTime(displaytime)
                                board.append({
                                    "line": linenumber,
                                    "departure": displaytime,
                                    "destination": destination,
                                    'time': diff,
                                    'deviations': deviations
                                })
            self._board = sorted(board, key=lambda k: k['time'])
        else:
            self._board.clear()
            # _LOGGER.info(self._board)


class SlDepartureBoardData(object):
    """ Class for retrieving API data """

    def __init__(self, apikey, siteid, timewindow):
        """Initialize the data object."""
        self._apikey = apikey
        self._siteid = siteid
        self._timewindow = timewindow
        self.data = {}

    @Throttle(MIN_UPDATE_FREQUENCY)
    def update(self, **kwargs):
        """Get the latest data for this site from the API."""
        import requests

        try:
            _LOGGER.info("fetching SL Data for '%s'", self._siteid)
            url = "{}{}{}{}{}{}".format(
                "https://api.sl.se/api2/realtimedeparturesV4.json?key=",
                self._apikey,
                "&siteid=",
                self._siteid,
                "&timewindow=",
                self._timewindow
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
