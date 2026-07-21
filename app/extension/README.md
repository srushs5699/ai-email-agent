# AI Email Agent LinkedIn Capture Extension

The extension captures only visible details from a LinkedIn post, lets you edit them, and opens the existing outreach form. It does not create a draft, queue item, generated email, approval, or send.

## Local setup

The extension reuses the repository frontend development dependencies. Run `cd app/frontend && npm install` once, then run `cd ../extension && npm run test`, `npm run lint`, `npm run typecheck`, and `npm run build`. The unpacked extension is `app/extension/dist`.

Its default application origin is `http://localhost:5173`. To use another local configured origin, update the extension's `appOrigin` setting through extension storage and add that narrow origin to `manifest.json` before rebuilding; never use secrets.

In Chrome, open `chrome://extensions`, enable **Developer mode**, choose **Load unpacked**, and select `app/extension/dist`. Reload the extension after rebuilding. Open a supported LinkedIn post, use the extension button, review/edit the capture, then select **Send to App**. The application opens its existing Outreach page for further manual completion. If extraction fails, select **Open manual entry** or use the normal application workflow directly.

## Permissions

- `activeTab` reads only the current tab after the user opens the popup.
- `storage` holds one short-lived pending import and optional local app-origin configuration.
- `tabs` opens the existing application after explicit confirmation.
- LinkedIn host access runs the narrowly scoped content script; localhost access delivers the import only to the local application bridge.
