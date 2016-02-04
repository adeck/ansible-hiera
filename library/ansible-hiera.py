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

# TODO -- update documentation to reflect argument syntax change
# TODO -- update examples to reflect argument syntax change

# TODO -- figure out if it's not a local_action and fail in that case, rather
#         than running whatever ruby script that has the right name and is in
#         /tmp .
# TODO -- improve examples section

DOCUMENTATION = """
---
module: hiera
description: "An ansible module used to query puppetlabs' hiera backend."
author: "Andrew Deck, github.com/adeck"
requirements:
  - >
    This module requires that the hiera ruby library is loadable in ruby by default.
    If you have a puppet agent or master installed on the system, this is already done.
    For more information about hiera, see U(https://github.com/puppetlabs/hiera)
notes:
  - >
    !IMPORTANT!
    Whenever an ansible module sets facts, ansible performs postprocessing on
    all those facts. Specifically, if the value of a fact is a string, ansible
    will _attempt to interpret that string as YAML_, and if it succeeds it
    will set the value of the fact to the result. See the EXAMPLES to get a
    feel for how seriously bad that can be. Again, this is an issue that has
    _nothing to do_ with this particular module; all the messed-up stuff
    happens after this module has exited.
    
    If a variable is not defined in hiera, it will be left undefined in ansible
    (or, at least, its value in ansible will _not be changed_. So, it may
    still have a value within ansible IFF it already had a value in ansible).
    
    This module is written so that querying all the variables only requires the
    ruby interpreter to be spawned once, and the hiera hierarchy only needs to
    be parsed once (or, at least, only one Hiera object is constructed in the
    ruby code). While it is possible to use this module in a with_items loop,
    defining each variable with a separate module call, it's far more
    efficient (and fast) to run it only once for each scope.
    
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
    
    If you still experience problems, please contact the author, Andrew Deck.
options:
  keys:
    description:
      - >
        This is a list of dictionaries. Each dictionary in that list
        must define the key 'hiera' (sans quotes), which must map to a string
        (the hiera-resolvable name of the variable you wish to access).
      - >
        When accessing globals, do not use the '::var_name' syntax. Simply specify
        'var_name'. If you prepend '::', the variable won't resolve, and as a result
        it will remain undefined.
      - >
        Each dictionary may also define the key 'ansible', which must also map
        to a string (the ansible identifier you want to use for that hiera
        variable). If the 'ansible' key is left undefined, this module will
        simply behave as if the 'ansible' key _was_ defined, and the value
        used will simply be the hiera identifier with all ':'
        characters replaced by '_' characters.
      - >
        Duplicate keys within the list are not treated specially. This means
        that, if two list entries have the same hiera key mapped to different
        ansible keys, both ansible keys will be defined. If two hiera keys map
        to the same ansible key, the value later in the list will "win". It's
        worth noting that, when two different hiera keys are mapped to the same
        ansible key, both hiera variables are resolved even if only one is
        used. In fact, every list item results in a hiera query.
        So, if you're resolving a lot of variables, it may be worthwhile
        to ensure there are no duplicate hiera keys _or_ duplicate ansible
        keys.
    required: yes
    aliases: ['names']
    type: list
  config_file:
    description:
      - >
        The YAML-format config file hiera uses.
        See hiera documentation for more information.
    required: yes
    aliases: ['hiera_config_file']
    type: string
  allow_empty:
    description:
      - >
        By default, if you leave 'keys' as an empty list, that is not an
        error condition. Hiera will still be run, but no variables will be resolved
        in hiera and no variables will be defined in ansible. This is useful if
        you dynamically define the list of hiera variables you'd want to use and
        that list may be empty. It's also useful if you just want to test that
        everything's configured correctly with hiera and you don't actually want to
        define anything. That having been said, if you set this (optional) parameter
        'allow_empty' to false, an empty list of 'keys' will be treated as
        an error condition.
    required: no
    default: yes
    type: bool
  scope_file:
    description:
      - The path to a YAML-formatted dictionary file.
      - >
        This is not interpreted by ansible, python, or hiera. It simply uses
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

EXAMPLES = """

Let's say you have this next line in one of your hiera files:

  test::var9: "[\\"hello\\", \\"{{ ansible_nodename }}\\", ansible_nodename]"

A perfectly innocent, decent string. Here's what ansible interprets it as:

  "test__var9": [
      "hello", 
      "{# ansible_nodename #}", 
      "my-hostname"
  ]

Clearly, there are situations within which this would be less than ideal.
The overwhelming majority of the time, it's worth pointing out, you won't
run into this. It won't try to coerce a string into an int, float, bool, or
other primitive. it won't try to coerce a string that happens to be a variable
name into that variable
(i.e. it won't replace a variable containing "ansible_nodename" with the actual
value of the ansible_nodename variable), and it won't try to coerce anything
that wouldn't otherwise be considered well-formed JSON.

It will, however, get very annoying very fast if you start using a lot of
curly braces, or if you wrap strings in brackets. So be careful.
"""

import os
import subprocess
import json
import re
from ansible.module_utils.basic import *

hiera_json_name = './library/hiera-json.rb'
hiera_json = hiera_json_name
## this doesn't work, because ansible actually copies the module contents into
##   the body of a much longer file, and then runs that.
# os.path.join(os.path.dirname(__file__), hiera_json_name)

def main():
  module = define_module()
  params = module.params
  try:
    facts = rename_vars(get_vars(construct_args(params)), params)
    module.exit_json(ansible_facts=facts)
  except Exception, e:
    module.fail_json(msg=str(e))

def define_module():
  module = AnsibleModule(
      argument_spec = dict(
          keys=dict(required=True, aliases=['names'], type='list'),
          config_file=dict(required=True, aliases=['hiera_config_file'], type='path'),
          allow_empty=dict(required=False, default=True, type='bool'),
          scope_file=dict(required=False, type='path'),
          scope=dict(required=False, type='dict'),
      )
      ,supports_check_mode=True
  )
  if module.check_mode:
    # check if any changes would be made but don't actually make those changes
    # in our case, this is a moot point.
    module.exit_json(changed=False)
  try:
    validate_args(module, module.params)
  except Exception, e:
    module.fail_json(msg='Your arguments were malformed and that resulted ' +
                          "in this exception: '" + str(e) + "'")
    
  #validate_ans_names(module, module.params)
  return module

def validate_args(module, params):
  validate_keys(module, params)

def validate_keys(module, params):
  keys = params['keys']
  for key in keys:
    hiera = key['hiera']
    if not (hiera and isinstance(key, basestring)):
      raise Exception("Every list item in 'keys' must have a key called "
                      "'hiera', and the value associated with that key must "
                      "be a string.")
    key['ansible'] = validate_ansible_key(hiera, key['ansible'])
  if not params['allow_empty'] and keys == []:
    module.fail_json(msg="'keys' was an empty list, and you "
                    "explicitly set the 'allow_empty' parameter to false.")

def validate_ansible_key(hiera_key, ansible_key):
  if not ansible_key:
    ansible_key = hiera_key.replace(':', '_')
  regex = '^[a-zA-Z_][a-zA-Z_0-9]*$'
  if not (isinstance(ansible_key, basestring) and re.match(regex, ansible_key)):
      raise Exception("an ansible key contained the value \"" + str(ident) +
                      "\" which did not match the regex " + regex)
  return ansible_key

def construct_args(params):
  pargs = [ hiera_json ]
  pargs.extend(['-c', params['config_file']])
  scope_file = params['scope_file']
  if scope_file:
      pargs.extend(['-f', scope_file])
  scope = params['scope']
  if scope:
      pargs.extend(['-j', json.dumps(scope)])
  pargs.append('--')
  pargs.extend([ key['hiera'] for key in params['keys'] ])
  return pargs

def get_vars(pargs):
  p = subprocess.Popen(pargs
        ,stdout = subprocess.PIPE
        ,stderr = subprocess.PIPE)
  res, err = p.communicate()
  # worth noting that res should never be None; even if keys was an
  #   empty list (which is entirely allowed), the result of running hiera
  #   should be "{}", not "".
  if p.returncode != 0 or res is None:
    raise Exception("Ruby code yielded return code " + str(p.returncode) +
                    " and error message: " + err)
  return json.loads(res)

def rename_vars(orig, params):
  # where 'orig' is in the form output by get_vars() above
  facts = {}
  for key in param['keys']:
    val = orig[key['hiera']]
    if val['defined']:
      facts[key['ansible']] = val['value']
  return facts

if __name__ == '__main__':
  main()

