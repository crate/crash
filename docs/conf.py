from crate.theme.rtd.conf.crate_crash import *

# Enable version chooser.
html_context.update({
    "display_version": True,
})

linkcheck_ignore += [
    # 403 Client Error: Forbidden
    r"https://www.wikiwand.com/.*",
]
