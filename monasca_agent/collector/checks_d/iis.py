# (C) Copyright 2015 Hewlett Packard Enterprise Development Company LP
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

'''
Check the performance counters from IIS
'''
try:
    import wmi
except Exception:
    wmi = None

from monasca_agent.collector.checks import AgentCheck


class IIS(AgentCheck):
    METRICS = [
        ('iis.uptime', 'gauge', 'ServiceUptime'),

        # Network
        ('iis.net.bytes_sent', 'rate', 'TotalBytesSent'),
        ('iis.net.bytes_rcvd', 'rate', 'TotalBytesReceived'),
        ('iis.net.bytes_total', 'rate', 'TotalBytesTransferred'),
        ('iis.net.num_connections', 'gauge', 'CurrentConnections'),
        ('iis.net.files_sent', 'rate', 'TotalFilesSent'),
        ('iis.net.files_rcvd', 'rate', 'TotalFilesReceived'),
        ('iis.net.connection_attempts', 'rate', 'TotalConnectionAttemptsAllInstances'),

        # HTTP Methods
        ('iis.httpd_request_method.get', 'rate', 'TotalGetRequests'),
        ('iis.httpd_request_method.post', 'rate', 'TotalPostRequests'),
        ('iis.httpd_request_method.head', 'rate', 'TotalHeadRequests'),
        ('iis.httpd_request_method.put', 'rate', 'TotalPutRequests'),
        ('iis.httpd_request_method.delete', 'rate', 'TotalDeleteRequests'),
        ('iis.httpd_request_method.options', 'rate', 'TotalOptionsRequests'),
        ('iis.httpd_request_method.trace', 'rate', 'TotalTraceRequests'),

        # Errors
        ('iis.errors.not_found', 'rate', 'TotalNotFoundErrors'),
        ('iis.errors.locked', 'rate', 'TotalLockedErrors'),

        # Users
        ('iis.users.anon', 'rate', 'TotalAnonymousUsers'),
        ('iis.users.nonanon', 'rate', 'TotalNonAnonymousUsers'),

        # Requests
        ('iis.requests.cgi', 'rate', 'TotalCGIRequests'),
        ('iis.requests.isapi', 'rate', 'TotalISAPIExtensionRequests'),
    ]

    def __init__(self, name, init_config, agent_config):
        AgentCheck.__init__(self, name, init_config, agent_config)
        self.wmi_conns = {}

    def _get_wmi_conn(self, host, user, password):
        key = "%s:%s:%s" % (host, user, password)
        if key not in self.wmi_conns:
            self.wmi_conns[key] = wmi.WMI(computer=host, user=user,
                                          password=password)
        return self.wmi_conns[key]

    def check(self, instance):
        if wmi is None:
            raise Exception("Missing 'wmi' module")

        # Connect to the WMI provider
        host = instance.get('host', None)
        user = instance.get('username', None)
        password = instance.get('password', None)
        dimensions = self._set_dimensions(None, instance)
        sites = instance.get('sites', ['_Total'])
        w = self._get_wmi_conn(host, user, password)

        try:
            wmi_cls = w.Win32_PerfFormattedData_W3SVC_WebService()
            if not wmi_cls:
                raise Exception('Missing data from Win32_PerfFormattedData_W3SVC_WebService')
        except Exception:
            self.log.exception('Unable to fetch Win32_PerfFormattedData_W3SVC_WebService class')
            return

        # Iterate over every IIS site
        for iis_site in wmi_cls:
            # Skip any sites we don't specifically want.
            if iis_site.Name not in sites:
                continue

            # Tag with the site name if we're not using the aggregate
            if iis_site.Name == '_Total':
                dimensions.pop('site', None)
            else:
                dimensions.update({'site': iis_site.Name})

            for metric, mtype, wmi_val in self.METRICS:
                if not hasattr(iis_site, wmi_val):
                    self.log.warn('Unable to fetch metric %s. Missing %s in '
                                  'Win32_PerfFormattedData_W3SVC_WebService' % (metric, wmi_val))
                    continue

                # Submit the metric value with the correct type
                value = float(getattr(iis_site, wmi_val))
                metric_func = getattr(self, mtype)
                metric_func(metric, value, dimensions=dimensions)
