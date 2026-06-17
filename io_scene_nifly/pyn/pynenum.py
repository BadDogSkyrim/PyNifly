"""
Enums that know how to parse themselves from strings and return human-readable names.
"""

from enum import IntFlag, IntEnum
import logging
log = logging.getLogger('pynifly')

class PynIntFlag(IntFlag):
    @property
    def fullname(self):
        """Return a concatenationg of all flags in human-readable format."""
        s = []
        for f in type(self):
            if f in self:
                s.append(f)
        return " | ".join(list(map(lambda x: x.name, s)))

    @classmethod
    def parse(cls, value):
        """Parse a string of concatenated flags into a single integer value."""
        try:
            if len(value) == 0:
                return 0
        except TypeError:
            pass

        try: 
            return int(value)
        except ValueError:
            pass

        valuelist = value.split("|")
        flags = 0
        for v in valuelist:
            have_val = False
            vclean = v.strip()
            try:
                flags |= cls[vclean]
                have_val = True
            except:
                pass
            if not have_val:
                log.debug(f"Unknown flag value: {vclean} for {cls.__name__}")
                # Might still be a raw numeric value (e.g. "0x10"); if not, skip it
                # rather than crashing the whole parse--an unknown name shouldn't
                # take down an export.
                try:
                    flags |= int(vclean, 0)
                except ValueError:
                    pass

        return flags


class PynIntEnum(IntEnum):
    @property
    def fullname(self):
        """Return the name of the enum value."""
        return self.name

    @classmethod
    def parse(cls, nm):
        """Return the value of the enum."""
        return cls[nm].value

