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

Curious how to use the ansible module?
It contains a DOCUMENTATION string readable by `ansible-doc`! Simply run:

    cd library
    ansible-doc -M . ansible-hiera.py

If you need a concrete example, look at `tests/site.yml`.
To run the example, run:

    cd tests
    ansible-playbook site.yml

Curious how to use the ruby app? It's also comes with its own documentation!
Simply run:

    ./library/hiera-json.rb --help

If the builtin documentation for the ruby executable isn't enough, you could
read the source of course (of course), or you could just look at the
hiera documentation (because the terms used in one mean the same thing in
the other), or simply
play with these things. Since the module (and the ruby script) don't modify
anything, there's no chance you could break anything by playing with them.

[hiera]: https://github.com/puppetlabs/hiera
[ansible]: http://www.ansible.com
[puppet]: https://puppetlabs.com

[gist]: https://gist.github.com/mrbanzai/8720298
<!--
  This gist was the original inspiration, and initially I was going to use
    a very similar approach. However, I quickly discovered that approach
    was pretty nightmarish and terrible, so I deleted all that code and started
    again from scratch.
  That gist is the original reason I made this code open source, because I
    was basing this code off that code and I wanted to be compliant with
    copyright rules. However, now that the two programs share no meaningful
    similarities, this doesn't need to be open source I suppose.
  That having been said, it's a useful tool, so open source it is.
  Happy hacking! :)
 -->
