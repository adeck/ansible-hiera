#!/bin/env python

import os
import subprocess
import json
# never call yaml.load(). Not Even Once(TM).
from yaml import safe_load as from_yaml

def from_yaml(obj):
    return yaml.safe_load(obj)

def is_list(obj):
  if isinstance(obj, basestring):
    return True
  else:
    try:
      for x in obj: break
      return True
    except TypeError:
      return False
      
class Hiera():
  def __init__(self, config_file, scope={}, namespace=''):
    """\
    Here, 'namespace' is just a string prepended to all variable names
      before defining them or looking them up. Worth noting that, before
      being passed to hiera, the namespace has '::' appended to it, so
      if left blank the default namespace becomes the global namespace.
    So if, for example, you specified namespace "postgres::server", and
      tried to look up variable "port", hiera would be queried for
      "postgres::server::port". And if you left the namespace as "",
      and you queried for, say, "environment", you'd get "::environment".

    'scope' means the same thing as it means in the hiera
      documentation; it's a
      hash of variables that must be defined outside the hierarchy
      itself. So if, for example, you have a hierarchy element
      with the path "hosts/%{hostname}", you'd probably want to do
      something like:
      scope = {
        'hostname' : 'example.com'
      }
      hiera_obj = Hiera('blah.yaml', scope)

    'config_file' is what it sounds like. It's the config file for
      hiera to use (see the '-c' flag in the hiera documentation for
      more information).
    """
    self.config_file = config_file
    self.scope = scope
    self.namespace = namespace + '::'

  # this is defined separately to make it easier to deprecate in future,
  #   since ideally this thing would simply be calling ruby compatibility
  #   libraries, rather than doing cringeworthy analysis of string
  #   output. The reason it's not currently using the ruby library is that
  #   the documentation on that is literally nonexistant, and it doesn't look
  #   like Puppet intended that API to be public, anyway. If that situation
  #   improves, this too will improve.
  def set_executable(self, hiera_executable_path = 'hiera'):
    """\
    This method must be called after initialization but before any
      other methods are called. The argument- hiera_executable_path-
      should point to the hiera executable you'd like to use for
      resolution.
    """
    self.hiera_exec = hiera_executable_path

  def get_var(self, var_name):
    """\
    Attempts to retrieve the variable of name self.namespace + var_name
      from hiera. If the variable isn't defined, returns None. If
      it's impossible to determine the type information associated with
      the variable, or something else manages to go wrong (e.g.
      incompatible YAML formatting), this will raise an exception.
    This code differentiates between the following:
    - list
    - hash
    - scalar
    
    'scalar' is a catchall for all the non-list, non-dictionary datatypes that
      the YAML parser we're using can differentiate between (e.g. string,
      boolean, int). That's entirely delegated to the YAML parser.

    Note: There are circumstances where this will fail despite the
      variable being defined in a way hiera considers acceptable.
    For example, if an outer scope defined
      a variable as a hash, and an inner scope defined that same
      variable as a list, this method will fail.
    There are two reasons for that failure.
      - I don't know the hiera code well enough to be
        able to determine accurately whether hiera is erroring out
        because it's in this case, or because it's in some other
        failing edge case, so it makes more sense to fail than to
        risk misinterpreting the variable, and
      - it's frankly abysmal coding style to use the same name for
        two variables of different datatypes depending on scope, and
        the additional effort required to support this functionality
        would be in aid of an abhorrent end goal. Fundamentally, if you're
        doing that, you deserve to see an error message at some point.
    """
# TODO -- handle YAML typing (i.e. differentiate between scalar string,
#         boolean, float, int, etc. The most common YAML standard types,
#         or at least the types explicitly mentioned in the docstring
#         above.
    _hash = self._run_hiera('hash', var_name)
    if _hash.rc == 0:
      if _hash.output == 'nil':
        return None
      return from_yaml(_hash.output)
    _list = self._run_hiera('list', var_name)
    if _list.rc != 0:
      raise Exception("Hiera was unable to interpret the variable named \"" + var_name + "\"as either a hash or a list. Even undefined variables and scalars are usually able to be interpreted as lists, and since the variable must be either undefined, a hash, a scalar, or a list, I'm not sure how to recover. Here's the hiera error output: ```" + _list.err + "```")
    _var = self._run_hiera('var', var_name)
    if _var.rc == 0:
      return self._determine_if_list_or_scalar(_list, _var)
    else:
      raise Exception("Hiera errored out on attempting to resolve the " +
                      "variable \"" + var_name + "\". To clarify, this does " +
                      "not mean the variable was udnefined. It means " +
                      "something *very* strange just happened. Here's the " +
                      "hiera error output: ```" + _var.err  + "```")

  def _run_hiera(self, datatype, var_name):
    """\
    Runs hiera in an attempt to resolve the variable with name var_name
      and type datatype.
    'datatype' must be one of the values accepted by
      _construct_hiera_commandline

    The return value is a hash with the following keys:
    - "output" (everything written to stdout, minus the newline character at the end)
    - "err" (everything written to stderr)
    - "rc" (the return code from invoking hiera)
    """
    hiera_args = self._construct_hiera_commandline(datatype, var_name)
    p = subprocess.Popen(hiera_args,
                          stdout = subprocess.PIPE,
                          stderr = subprocess.PIPE)
    res, err = p.communicate()
    if res is None: res = ''
    if err is None: err = ''
    # removes trailing newline from 'output'
    if res != '' and res[-1] == '\n':
      res = res[:-1]
    return {
      'output' : res
      ,'err' : err
      ,'rc' : p.returncode
    }

  def _construct_hiera_commandline(self, datatype, var_name):
    """\
    Puts together a list of arguments for the command line invocation of hiera.

    datatype must be one of:
    - "var" (for all scalar variables- strings, ints, floats, booleans, ec.)
    - "list" (for lists / arrays)
    - "hash" (for hashes / dictionaries)
    """
    hiera_args = [self.hiera_exec, '-c', self.config_file]
    if datatype == 'var':
      pass # do nothing
    elif datatype == 'list':
      hiera_args.append('-a')
    elif datatype == 'hash':
      hiera_args.append('-h')
    else:
      raise Exception("You gave an invalid datatype of \"" + datatype + "\" for the variable \"" + var_name + "\". Datatype must be one of \"var\", \"list\", or \"hash\". See the _construct_hiera_commandline method docstring for details.")
    hiera_args.append(self.namespace + var_name)
    for key, value in self.scope:
      hiera_args.append(self.namespace + key + '=' + value)
    return hiera_args

  def _determine_if_list_or_scalar(_list, _var):
    list_obj = from_yaml(_list.output)
    var_list_obj = None
    got_var_list_obj = False
    if len(list_obj) > 0 and _var.output == list_obj[0]:
      return _var.output
    try:
      var_list_obj = from_yaml(_var.output)
      got_var_list_obj = True
    except:
      pass # do nothing
    if got_var_list_obj:
      if var_list_obj == []:
        if list_obj == []:
          return []
        elif _var.output == "[]":
          if list_obj[0] == "[]":
            raise Exception("Can't determine whether the variable is the " +
                            "string \"[]\" or an actual empty list.")
          else: # list_obj[0] != "[]"
            return []
        # this case could happen if, for example, we had the string "[     ]"
        else:
          raise Exception("The string version of the variable resolved to " +
                          "an empty list, but was not '[]', and the first " +
                          "element of the list version of the variable was " +
                          "not the same as the string version. If hiera " +
                          "always renders empty lists as '[]', this case " +
                          "should never happen.")
      elif is_list(var_list_obj):
        if len(list_obj) >= len(var_list_obj):
          for i in xrange(var_list_obj):
            if var_list_obj[i] != list_obj[i]:
              break
          else:
            return var_list_obj
        if list_obj == []:
          raise Exception("Somehow, the string version of the variable " +
                          "resolved to a nonempty YAML list variable " +
                          "while the list version resolved to an empty list. " +
                          "Since the technical term for that circumstance is " +
                          "``Looney Toons'', I'm erroring out.")
      else: # var isn't list
        if list_obj == []:
          if _var.output == "":
            return None
          else:
            raise Exception("The string version of the variable was \"" +
                            + _var.output + "\", but the list version of " +
                            "the variable was an empty list.")
      first_li = None
      got_first_li = False
      try:
        first_li = from_yaml(list_obj[0])
        got_first_li = True
      except:
        pass # do nothing
      if got_first_li and first_li == var_list_obj:
        return list_obj[0]
      raise Exception("The string version of your variable resolved to " +
                      "a YAML list, which was neither the prefix of the " +
                      "list version of your variable, nor was it the " +
                      "first element of the list form of the variable. ")
    else: # !got_var_list_obj
      if list_obj == []:
        if _var.output == "":
          return None
        else:
          raise Exception("The variable's string representation was not an " +
                          "empty string, but its list representation was an " +
                          "empty list. That shouldn't happen.")
      else: # list_obj != []
        raise Exception("Couldn't determine variable type.")


