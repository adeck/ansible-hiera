#!/bin/env python

import os
import subprocess
import json

def main():
    module = AnsibleModule(
        argument_spec = dict(
            name=dict(aliases=['key']),
            fact=dict(required=False),
            path=dict(required=False, default="hiera"),
            context=dict(required=False, default={}, type='dict'),
            source=dict(required=False, default=None)
        )
    )

    params = module.params
    out = {}

    if not params['fact']:
        params['fact'] = params['name']

    try:
        pargs = [
            params['path'],
            '-f', 'json'
        ]
        if params['source']:
            pargs.extend(['-c', params['source']])

        pargs.append(params['name'])

        pargs.extend([r'%s=%s' % (k, v) for k, v in params['context'].iteritems()])

        p = subprocess.Popen(pargs, stdout=subprocess.PIPE)
        res, err = p.communicate()

        if res is None:
            res = ""
        else:
            res = json.loads(res)

        out['ansible_facts'] = {}
        out['ansible_facts'][params['fact']] = res

        module.exit_json(**out)

    except Exception, e:
        module.fail_json(msg=str(e))

from ansible.module_utils.basic import *
main()
