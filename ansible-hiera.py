#!/usr/bin/env python2
#
# An ansible module which runs a ruby module which uses the hiera API to
#   query hiera and translate the results into unambiguous JSON.
#
# While I could have written the entire ansible module in ruby, library
#   support for ansible only exists in python, and library support for hiera
#   only exists in ruby. The extra logic required to glue the applications
#   together is nothing compared to the headache that is creating and
#   maintaining a separate ruby ansible compatibility library from scratch.
# And it's hopefully blatantly obvious that writing and maintaining a python
#   port of hiera or a python hiera compatibility library is far, far worse.
#

# TODO -- add examples section

DOCUMENTATION = """
---
module: ansible-hiera
short_description: "An ansible module used to query puppetlabs' hiera backend."
author: "Andrew Deck, @adeck"
requirements:
  - This module requires that the hiera ruby library is loadable in ruby by default. If you have a puppet agent or master installed on the system, this is already done.
  - For more information about hiera, see U(https://github.com/puppetlabs/hiera)
notes:
  - >
    This module is written so that querying all the variables only require the
    ruby interpreter to be spawned once, and the hiera hierarchy only needs to
    be parsed once (or, at least, only one Hiera object is constructed in the
    ruby code). While it is possible to use this module in a with_items loop,
    defining each variable with a separate module call, it's far more
    efficient (and fast) to run it only once for each scope.
  - If a variable is not defined in hiera, it will be left undefined in ansible.
  - >
    There are two executables which act in tandem to accomplish the goals of
    this module: the python part (which interacts with ansible) and the ruby
    part (which uses the hiera ruby API). This is done to ensure that, should
    some aspect of hiera or ansible change, those changes will most likely not
    affect this module's operation, because the library interfaces (hopefully)
    remain unaffected.
  - >
    For more information on how the backend works, or if you just want access
    to hiera objects as JSON directly, try running the ruby script that
    accompanies / is used by this module. It's intended to be user-friendly
    and is a useful tool all by itself.
options:
  hiera_names:
    description:
      - The list of hiera-resolvable names of the variables you wish to access.
      - >
        This list may contain duplicate entries (if you want to map one variable
        in hiera to multiple ansible variables, for example).
      - >
        When accessing globals, do not use the '::var_name' syntax. Simply specify
        'var_name'. If you prepend '::', the variable won't resolve, and as a result
        it will remain undefined.
    required: yes
    aliases: ['keys', 'p_keys']
    type: list
  allow_empty:
    description:
      - >
        By default, if you leave 'hiera_names' as an empty list, that is not an
        error condition. Hiera will still be run, but no variables will be resolved
        in hiera and no variables will be defined in ansible. This is useful if
        you dynamically define the list of hiera variables you'd want to use and
        that list may be empty. It's also useful if you just want to test that
        everything's configured correctly with hiera and you don't actually want to
        define anything. That having been said, if you set this (optional) parameter
        'allow_empty' to true, an empty list of 'hiera_names' will be treated as
        an error condition.
    required: no
    default: yes
    type: bool
  ansible_names:
    description:
      - >
        The list of identifiers you want ansible to use for the variables
        in the 'hiera_names' list. This list, if defined, must be the same
        length as the 'hiera_names' list.
      - >
        Duplicate entries are allowed, and they are not treated specially. So
        if you say hiera 'test::var1' should map to ansible variable 'bla',
        and later in the two lists you specify 'test::var2' should map to
        ansible variable 'bla', the value associated with 'test::var2' in hiera
        will be the one assigned to ansible variable 'bla'. However, doing this
        is discouraged, since hiera is still queried for all the names in
        the 'hiera_names' list, so even the overridden names will be resolved.
      - >
        If this is left undefined, the default behavior is to simply replace
        all ':' characters in the corresponding 'hiera_names' with '_'
        characters, and then attempt to validate the result as an ansible
        identifier.
    required: no
    type: list
  scope_file:
    description:
      - The path to a YAML-formatted dictionary file.
      - >
        This is not interpreted by ansible python, or hiera. It simply uses
        ruby's YAML interpreter.
        Primarily useful for when your hierarchy contains parameterized
        paths.
      - >
        The variables defined in the 'scope' parameter have higher precedence than
        those defined in the 'scope_file'. So, if a variable is defined in
        'scope_file' and also defined in 'scope', the value used in 'scope' will
        be the one used.
    required: no
    type: string
  scope:
    description:
      - A dictionary of name-value mappings passed to hiera.
      - >
        The variables defined in the 'scope' parameter have higher precedence than
        those defined in the 'scope_file'. So, if a variable is defined in
        'scope_file' and also defined in 'scope', the value used in 'scope' will
        be the one used.
    required: no
    type: dict
"""

import os
import subprocess
import json
import re
from ansible.module_utils.basic import *

hiera_json = './hiera-json.rb'

def main():
  module = define_module()
  params = module.params
  try:
    out = {}
    out['ansible_facts'] = decode_vars(get_vars(construct_args(params)), params)
    module.exit_json(out)
  except Exception, e:
    module.fail_json(msg=str(e))

def define_module():
  module = AnsibleModule(
      argument_spec = dict(
          hiera_names=dict(required=True, aliases=['keys', 'p_keys'], type='list'),
          # specifies whether the hiera_names parameter is allowed to be
          #   an empty list.
          allow_empty=dict(required=False, default=True, type='bool'),
          ansible_names=dict(required=False, type='list'),
          scope_file=dict(required=False, type='string'),
          scope=dict(required=False, type='dict'),
      )
  )
  validate_hiera_names(module, module.params)
  validate_ans_names(module, module.params)
  return module

def validate_hiera_names(module, params):
  h_names = params['hiera_names']
  for key in h_names:
    if not isinstance(key, basestring):
      module.fail_json(msg='Parameter "' + str(key) + '" in hiera_names is ' +
                      'not a string. These names must be strings.')
  if not params['allow_empty'] and h_names == []:
    module.fail_json(msg="'hiera_names' was an empty list, and you " +
                      "explicitly set the 'allow_empty' parameter to false.")

def validate_ans_names(module, params):
  regex = '^[a-zA-Z_][a-zA-Z_0-9]*$'
  ans_names_usage = "Argument 'ansible_names', if defined, must be a list " +
                    "of ansible-compatible names (so, valid python " +
                    "identifiers which are of the form " + 
                    + regex + "). Since these names " +
                    "correspond to the names in 'hiera_names', those two " +
                    "lists must also be the same length. "
  ans_names = params['ansible_names']
  if not ans_names:
    params['ansible_names'] = [k.replace(':','_') for k in params['hiera_names']
    ans_names = params['ansible_names']
  if len(ans_names) != len(param['hiera_names']):
    module.fail_json(msg=ans_names_usage + 
                  "'ansible_names' and 'hiera_names' differed in length.")
  valid = re.compile(regex)
  for ident in ans_names:
    if not (isinstance(ident, basestring) and valid.match(ident)):
      module.fail_json(msg=ans_names_usage + 
                  "'ansible_names' contained the value \"" + str(ident) +
                  "\" which did not match the regex " + regex)

def construct_args(params):
  pargs = [ hiera_json ]
  scope_file = params['scope_file']
  if scope_file:
      pargs.extend(['-f', scope_file])
  scope = params['scope']
  if scope:
      pargs.extend(['-j', json.dumps(scope)])
  pargs.append('--')
  pargs.extend(params['hiera_keys'])
  return pargs

def get_vars(pargs):
  p = subprocess.Popen(pargs
        ,stdout = subprocess.PIPE
        ,stderr = subprocess.PIPE)
  res, err = p.communicate()
  # worth noting that res should never be None; even if hiera_names was an
  #   empty list (which is entirely allowed), the result of running hiera
  #   should be "{}", not "".
  if p.returncode != 0 or res is None:
    raise Exception("Ruby code yielded return code " + str(p.returncode) +
                    " and error message: " + err)
  return json.loads(res)

def decode_vars(encoded, params):
  # where 'encoded' is in the form output by get_vars() above
  h_keys = params['hiera_names']
  a_keys = params['ansible_names']
  facts = {}
  for i in xrange(len(h_keys)):
    val = encoded[h_keys[i]]
    if val['defined']:
      facts[a_keys[i]] = val['value']

if __name_ == '__main__':
  main()

