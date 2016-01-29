#!/usr/bin/env ruby
#
# A ruby module to get hiera variables in an unambiguous JSON format.
#
# You may be aware that there's already a hiera commandline tool.
# The hiera commandline tool simply stringifies ruby objects and returns
#   them in that ambiguous format, assuming you already know the type
#   information. Although the documentation isn't explicit about that,
#   the tool is intended for debugging: verifying that you get the answer you
#   expect, rather than actually resolving a value. Using it in an actual
#   application quickly alerts you to the fact that it's a buggy nightmare
#   and you made a terrible mistake.
#

require 'rubygems'
require 'json'
require 'hiera'
require 'puppet'
require 'optparse'

def main
  options = parse_options
  scope = get_scope(options)
  config_file = options[:config_file]
  hiera = Hiera.new(:config => config_file)
  result = {}
  until ARGV.empty?
    var_name = ARGV.shift
    result[var_name] = get_var(hiera, scope, var_name)
  end
  cout = IO.new STDOUT.fileno
  JSON.dump(result, cout)
  cout.flush
end

def get_scope(options)
  scope = {}
  scope_file = options[:yaml_scope_file]
  if not scope_file.nil?
    scope = YAML.load_file(scope_file)
  end
  scope_json = options[:json_scope]
  if not scope_json.nil?
    scope = scope.merge(JSON.load(scope_json))
  end
  return scope
end

def parse_options
  options = {}
  OptionParser.new do |opts|
    opts.banner = "Usage: #{$0} [options] [variable_name ...]"

    opts.on('-c', '--configfile FILENAME', 'Path to hiera config file') { |v| options[:config_file] = v }
    opts.on('-j', '--jsonscope JSON', 'A json-formatted dictionary of variables to add to the scope') { |v| options[:json_scope] = v }
    opts.on('-f', '--yamlscope FILENAME', 'A YAML formatted file containing a dictionary of variables to add to the scope') { |v| options[:yaml_scope_file] = v }
  end.parse!
  return options
end

def get_var(hiera, scope, var_name)
  result = hiera.lookup(var_name, nil, scope)
  return { "defined" => (not result.nil?) , "value" => result}
end

main

