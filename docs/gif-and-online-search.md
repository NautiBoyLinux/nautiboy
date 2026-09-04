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

GIPHY results remain in memory for the session and are never placed in the XDG
media cache. Attribution remains visible in the search interface. Production
distribution is deferred until external-LCD attribution policy is clarified.

Current provider references:

- <https://developers.giphy.com/docs/api/>
- <https://support.giphy.com/hc/en-us/articles/360028134111-GIPHY-API-Terms-of-Service>
- <https://developers.google.com/tenor/guides/quickstart>
