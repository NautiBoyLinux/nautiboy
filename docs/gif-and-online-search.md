# GIF playback and optional search

Local GIFs are read into a bounded encoded buffer, validated sequentially, and
decoded one frame at a time. Pillow supplies the composed canvas after GIF
transparency and disposal handling. Every LCD frame then uses the same Fit or
Center Crop renderer and baseline-JPEG encoder as static media.

The scheduler has no frame queue. A monotonic clock determines which frame is
current after each completed transfer; missed intermediate frames are discarded.
Frames held longer than one second are refreshed every 1,000 ms to retain
volatile software control. Disconnects and all backend errors stop playback
without retries. Restore and normal exit stop both GIF and static scheduling
before the validated hardware-mode restore reports are issued.

Online search is optional. A GIPHY API key may be saved from Preferences into
the desktop's Secret Service/KWallet-compatible keyring. The process-only
`NAUTIBOY_GIPHY_API_KEY` environment variable overrides a stored key. The key
is not stored in NautiBoy settings, displayed, or logged. Search metadata and media requests have finite timeouts,
are cancellable, require HTTPS and expected content types, and enforce response
size limits.

Browsing, trending results, thumbnails, and search responses remain transient
and are never placed in a persistent generic cache. When the user explicitly
chooses a GIPHY result with **Use GIF**, NautiBoy stores only that selected GIF
and minimal attribution/integrity metadata under
`$XDG_DATA_HOME/io.github.nautiboylinux.nautiboy/selected-media/` (falling back
to `~/.local/share`). GIF mode owns one deterministic slot and each Creative
preset owns one independent slot. Replacements overwrite only their own slot;
choosing local media removes the corresponding selected-GIPHY slot. Missing or
corrupt stored media is ignored safely and never causes an automatic LCD send.
No credential or search-response payload is stored with selected media.

Attribution remains visible in the search interface and restored media UI. The remaining
public-release gate is an acceptable production credential/distribution model
for an open-source Linux desktop application, together with confirmed licensing,
attribution, and external-LCD-use terms. No personal or beta API key may be
embedded in source, packages, or application defaults. Credential resolution
remains, in order: the process-only `NAUTIBOY_GIPHY_API_KEY` override, the
desktop keyring, then unconfigured. A proxy or hosted backend is not part of
this milestone and must not be introduced without a separate design decision.

On first credential access after the public-namespace migration, NautiBoy looks
for the current Secret Service name first. If it is absent and the provisional
development service `io.github.nautiboy.nautiboy` contains a key, NautiBoy
writes that value under `io.github.nautiboylinux.nautiboy` and removes the old
keyring item. The value never leaves Secret Service or enters settings/logs.

Current provider references:

- <https://developers.giphy.com/docs/api/>
- <https://support.giphy.com/hc/en-us/articles/360028134111-GIPHY-API-Terms-of-Service>
- <https://developers.google.com/tenor/guides/quickstart>
