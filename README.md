# ansible-hiera

## WARNING! PLEASE READ!

At the moment, this module relies upon the assumption that it is running on
the master, and that the user is running the playbook from the root of the
project (so modules are under `./library/`). However, if the module isn't
run as a `local_action` this is a serious security issue, because an attacker
could place a file under `./library/hiera-json.rb` on the slave machine, and
could use that to do whatever it wants.

## About

An ansible module for loading [hiera][] facts into [ansible][].

This is primarily useful for those looking to use [puppet][] alongside ansible.

[hiera]: https://github.com/puppetlabs/hiera
[ansible]: http://www.ansible.com
[gist]: https://gist.github.com/mrbanzai/8720298
[puppet]: https://puppetlabs.com
