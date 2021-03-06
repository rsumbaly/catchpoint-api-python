import sys
import base64
import datetime
import pytz
import requests


class CatchpointError(Exception):
    pass


class Catchpoint(object):

    def __init__(
        self,
        host="io.catchpoint.com",
        apiUri="ui/api/v1"
    ):
        """
        Basic init method.

        - host (str): The host to connect to
        - apiUri (str): The API's connection string
        """
        self.verbose = False
        self.host = host
        self.apiUri = apiUri
        self.contentType = "application/json"

        self._auth = False
        self._token = None

    def _debug(self, msg):
        """
        Debug output. Set self.verbose to True to enable.
        """
        if self.verbose:
            sys.stderr.write(msg + '\n')

    def _connectionError(self, e):
        msg = "Unable to reach {0}: {1}" .format(self.host, e)
        sys.exit(msg)

    def _authorize(self, creds):
        """
        Request an auth token.

        - creds: dict with client_id and client_secret
        """
        self._debug("Creating auth url...")
        uri = "https://{0}/ui/api/token" .format(self.host)
        payload = {
            'grant_type': 'client_credentials',
            'client_id': creds['client_id'],
            'client_secret': creds['client_secret']
        }

        # make request
        self._debug("Making auth request...")
        try:
            r = requests.post(uri, data=payload)
        except requests.ConnectionError, e:
            self._connectionError(e)

        self._debug("URL: " + r.url)
        data = r.json()

        self._token = data['access_token']
        self._debug("TOKEN: " + self._token)
        self._auth = True

    def _makeRequest(self, uri, params=None, data=None):
        """
        Make a request with an auth token.

        - uri: URI for the new Request object.
        - params: (optional) dict or bytes to be sent in the query string for the Request.
        - data: (optional) dict, bytes, or file-like object to send in the body of the Request.
        """
        self._debug("Making request...")
        headers = {
            'Accept': self.contentType,
            'Authorization': "Bearer " + base64.b64encode(self._token)
        }
        try:
            r = requests.get(uri, headers=headers, params=params, data=data)
            if r.status_code != 200:
                raise CatchpointError(r.content)
        except requests.ConnectionError, e:
            self._connectionError(e)

        self._debug("URL: " + r.url)
        try:
            r_data = r.json()
            self._expiredTokenCheck(r_data)
        except TypeError, e:
            return e
        return r_data

    def _expiredTokenCheck(self, data):
        """
        Determine whether the token is expired. While this check could
        technically be performed before each request, it's easier to offload
        retry logic onto the script using this class to avoid too many
        req/min.

        - data: The json data returned from the API call.
        """
        if "Message" in data:
            if data['Message'].find("Expired token") != -1:
                self._debug("Token was expired and has been cleared, try again...")
                self._token = None
                self._auth = False

    def _formatTime(self, startTime, endTime, tz):
        """
        Format "now" time to actual UTC time and set microseconds to 0.

        - startTime: start time of the requested data (least recent).
        - endTime: end time of the requested data (most recent).
        - tz: Timezone in tz database format (Catchpoint uses a different format).
        """
        if endTime is not None and startTime is not None:
            if endTime == "now":
                if not isinstance(startTime, int) and startTime >= 0:
                    msg = "When using relative times, startTime must be a negative number (number of minutes minus 'now')."
                    sys.exit(msg)
                try:
                    endTime = datetime.datetime.now(pytz.timezone(tz))
                    endTime = endTime.replace(microsecond=0)
                except pytz.UnknownTimeZoneError:
                    msg = "Unknown Timezone '{0}'\nUse tz database format: http://en.wikipedia.org/wiki/List_of_tz_database_time_zones" .format(tz)
                    sys.exit(msg)
                startTime = endTime + datetime.timedelta(minutes=int(startTime))
                startTime = startTime.strftime('%Y-%m-%dT%H:%M:%S')
                endTime = endTime.strftime('%Y-%m-%dT%H:%M:%S')
                self._debug("endTime: " + str(endTime))
                self._debug("startTime: " + str(startTime))

        return startTime, endTime


    def aggregated(self, creds, testIds, startTime, endTime, aggregationType, tz="UTC"):
	"""
	Retrieve aggregated data for a list of tests for a time period.
	"""
	if not self._auth:
	    self._authorize(creds)

        startTime, endTime = self._formatTime(startTime, endTime, tz)
   
        if aggregationType not in ["Day", "Minutes15"]:
	    msg = "Can only be Day or Minutes15"
            sys.exit(msg)	

        # prepare request
        self._debug("Creating aggregated url....")
        uri = "http://{0}/{1}/performance/aggregated" \
             .format(self.host, self.apiUri)
        params = {
            'tests': ",".join(testIds),
            'aggregationType': aggregationType,
            'startTime': startTime,
            'endTime': endTime
        }

        return self._makeRequest(uri, params)


    def raw(self, creds, testId, startTime, endTime, tz="UTC"):
        """
        Retrieve the raw performance chart data for a given test for a time period.
        """
        if not self._auth:
            self._authorize(creds)

        startTime, endTime = self._formatTime(startTime, endTime, tz)

        # prepare request
        self._debug("Creating raw_chart url...")
        uri = "https://{0}/{1}/performance/raw/{2}" \
            .format(self.host, self.apiUri, testId)
        params = {
            'startTime': startTime,
            'endTime': endTime
        }

        return self._makeRequest(uri, params)

    def favorite_charts(self, creds):
        """
        Retrieve the list of favorite charts.
        """
        if not self._auth:
            self._authorize(creds)

        # prepare request
        self._debug("Creating get_favorites url...")
        uri = "https://{0}/{1}/performance/favoriteCharts" \
            .format(self.host, self.apiUri)

        return self._makeRequest(uri)

    def favorite_details(self, creds, favId):
        """
        Retrieve the favorite chart details.
        """
        if not self._auth:
            self._authorize(creds)

        # prepare request
        self._debug("Creating favorite_details url...")
        uri = "https://{0}/{1}/performance/favoriteCharts/{2}" \
            .format(self.host, self.apiUri, favId)

        return self._makeRequest(uri)

    def favorite_data(
            self, creds, favId,
            startTime=None, endTime=None, tz="UTC", tests=None):
        """
        Retrieve the data for a favorite chart, optionally overriding its timeframe
        or test set.
        """
        if not self._auth:
            self._authorize(creds)

        startTime, endTime = self._formatTime(startTime, endTime, tz)

        # prepare request
        self._debug("Creating favorite_data url...")
        uri = "https://{0}/{1}/performance/favoriteCharts/{2}/data" \
            .format(self.host, self.apiUri, favId)

        if endTime is None or startTime is None:
            params = None
        else:
            params = {
                'startTime': startTime,
                'endTime': endTime
            }

        if tests is not None:
            params['tests'] = tests

        return self._makeRequest(uri, params)

    def nodes(self, creds):
        """
        Retrieve the list of nodes for the API consumer.
        """
        if not self._auth:
            self._authorize(creds)

        # prepare request
        self._debug("Creating nodes url...")
        uri = "https://{0}/{1}/nodes" \
            .format(self.host, self.apiUri)

        return self._makeRequest(uri)

    def node(self, creds, node):
        """
        Retrieve a given node for the API consumer.
        """
        if not self._auth:
            self._authorize(creds)

        self._debug("Creating node url...")
        uri = "https://{0}/{1}/nodes/{2}" \
            .format(self.host, self.apiUri, node)

        return self._makeRequest(uri)
