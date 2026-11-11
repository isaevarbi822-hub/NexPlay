# NEXPLAY — Steam & Epic Games Integrations

## Live services

- iPad website: https://nexplay-cloud.onrender.com/
- Accounts page: https://nexplay-cloud.onrender.com/stores.html
- API status: https://nexplay-accounts.onrender.com/api/status
- Steam OpenID start: https://nexplay-accounts.onrender.com/auth/steam/start

The account service uses the **Free** Render web-service plan and the Frankfurt region. Free services may spin down after 15 minutes of inactivity, then take time to wake up.

## Steam

Steam OpenID sign-in is implemented **without collecting a Steam password**. The login redirects to Steam's official website, Steam verifies the identity, and the NEXPLAY backend issues a short-lived signed token. Identity does **not** prove that games may be streamed.

Optional library import:

1. Obtain a Steam Web API key through the official Steam developer portal, if eligible.
2. Open the `nexplay-accounts` web service in Render → Environment.
3. Set `STEAM_WEB_API_KEY` there. Never commit this secret to GitHub and never paste it into a public chat.
4. Redeploy the accounts service. Use the accounts page to connect Steam and check available games.

The game list depends on Steam's API rules and the player's Steam privacy settings; a missing or private library is **not** proof that no games are owned.

Steam documentation: https://partner.steamgames.com/doc/features/auth and https://partner.steamgames.com/doc/webapi/iplayerservice

## Epic Games

Epic login is prepared but disabled until official Epic Developer Portal setup is completed. NEXPLAY **does not** supply fake or third-party Epic login forms.

If the Epic organization is eligible and the application passes the required review:

1. Create a product and Epic Account Services application in https://dev.epicgames.com/portal
2. Configure a linked client and `basic_profile` user permission as authorized by Epic.
3. Add precisely this redirect URL for the OAuth client:
   `https://nexplay-accounts.onrender.com/auth/epic/callback`
4. In Render → `nexplay-accounts` → Environment set the values `EPIC_CLIENT_ID`, `EPIC_CLIENT_SECRET`, and `EPIC_DEPLOYMENT_ID`.
5. Redeploy `nexplay-accounts`. The Epic login button will then become available when `/api/status` reports `epic_oauth_available=true`.

**Epic OAuth identity does not grant access to a user's entire Epic Games Store purchased library.** Epic entitlement APIs may be limited to products you are authorized to manage. Don't invent ownership data.

Epic documentation: https://dev.epicgames.com/docs/epic-online-services/accounts-and-social/eos-epic-account-services/getting-started

## Security and limitations

- Both providers own their password screens. NEXPLAY does not ask for Steam/Epic passwords.
- Identity tokens are held in the browser's `sessionStorage` (per tab), expire after 24 hours and can be removed from the account page. This is **not** yet a persistent NEXPLAY user account with cross-device sync.
- Steam/Epic account identity is **not** a cloud gaming license, cloud launch permission or game streaming capability.
- Current Render static site + Free Python auth server are not GPU gaming servers.
- The web UI shows official store links. Actual PC/cloud game launch and multi-user hosting will need separately authorized providers, GPU machines and additional engineering.
