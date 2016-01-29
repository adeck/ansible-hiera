#!/usr/bin/env bash

! which hiera && {
  echo no hiera installed
  exit 1
}

exe=./library/hiera-json.rb

get_vars() {
  $exe 2>/dev/null -f data/environ.yaml -c data/hiera.yaml $@
}

get_json_vars() {
  local json='{"datacenter": "ny-2","server_type": "database","server_name": "localhost"}'
  $exe 2>/dev/null -j "$json" -c data/hiera.yaml $@
}


echo 'testing multiple vars'
get_vars 'test::var9' 'test::var6'
echo

for i in {1..10}
do
  echo testing test::var$i
  one="$(get_vars "test::var$i")"
  two="$(get_json_vars "test::var$i")"
  # NOTE -- These won't always be the same, because ruby won't always print
  #         the keys in the same order for a dictionary, so visual comparison
  #         is the best way. I know that sounds tedious, but there are only ten
  #         variables. It takes, like, a minute to verify.
  [ "$one" == "$two" ] || {
    echo "!!!!! $two"
  }
  echo "$one"
done

