# AMP game servers (Hisho add-on)

## What it does

Shows your AMP (CubeCoders Application Management Panel) controllers on the Hisho dashboard: each
game-server instance, whether it is running, its players, CPU and memory, with Start and Stop
buttons. Hisho logs in to each panel once and reuses the session.

## What it needs

- You need:
  - An AMP (CubeCoders Application Management Panel) controller you can reach from the Core machine
  - An AMP user for Hisho alone (no two-factor sign-in) whose role can only start and stop instances, and its password
- Runs on: the Core machine, inside Hisho Core
- One entry per AMP panel, each with:
  - `url` (str, required)
  - `user` (str, required)
  - `password` (password, kept as a local secret, required)
  - `note` (str, optional)

## How to install

On the dashboard: **Add-ons > Store > AMP game servers > Install**. Or from a terminal:

```bash
hisho addon install amp
```

Hisho takes the newest version from this repository and turns it on inside Hisho Core. Updates show as **Update
available** on its Store card; **Roll back** returns to the version before.

## How to use

Its card on the overview lists each panel's game servers, running or stopped, with players. Its page (**Add-ons > AMP game servers**) has **Start** and **Stop** for each instance; both ask first.

## Settings

Its page lists the AMP panels it finds on your network (port 8080 showing AMP's sign-in page); **Use this**
fills in the address. AMP's API has no tokens, so Hisho keeps a login: make a user for Hisho alone. In the
AMP panel, **Configuration > Role Management**: a role (e.g. Hisho) with only Instance Management's **Start
Instance** and **Stop Instance** allowed, and the game servers it may see under **All Instances**; then
**Configuration > User Management**: a user (e.g. hisho) with that role, its own long password and no
two-factor sign-in ([AMP's guide to users and roles](https://discourse.cubecoders.com/t/managing-user-permissions-in-amp/2301)).

Add a panel on its page (**Add-ons > AMP game servers > + add**): its IP address (http and port
8080 assumed, or a full URL), that AMP user name and its password. A typed password is kept only on
the Core machine (`~/.hisho-secrets.env`); you can give a secret's name instead. Entries are kept
in `~/Hisho/System/Config/Addons/amp.yaml`. To change the password: AMP panel > Configuration >
User Management.

## How to remove

**Add-ons > Store > AMP game servers > Remove**, or `hisho addon remove amp`. Its card and page go away; your settings stay in `~/Hisho/System/Config/Addons/amp.yaml`, so installing it again picks up where you left off.

## License

Source-available under the [PolyForm Shield License 1.0.0](LICENSE.md): free to use, change and share,
for any purpose except offering a product that competes with Hisho (reselling it, for example).
