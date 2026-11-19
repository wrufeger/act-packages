---
name: homenet-add-device
description: Use when a new device or service joins the home network and should be reachable, named and documented. Ends with the device set up on the network side, in Home Assistant if it is used, entered in the docs and confirmed by a read of the live state.
---

# Add a device to the network

Result: the device has a stable address, a DNS name, a place in Home Assistant when that is in use, an entry in the
docs, and a reader has confirmed all of it from the live state. The orchestrator runs this skill; readers and the
writer are started by it, never by each other.

1. **Collect the facts from the owner.** What the device is, where it sits, how it connects (cable, WLAN, Zigbee, other),
   its purpose, and the name wanted. Look at the naming scheme in `docs/project/homenet/`; propose a name by that
   scheme and let the owner confirm. No scheme yet: propose one and write it down in the docs in step 7.
2. **Check the permission.** Find the rows of `docs/project/homenet/access.md` for the systems that will change (the
   router or controller, the DNS filter, Home Assistant). A change needs a standing entry for that action class, or a
   dated approval for this case (`R-safe-approval`). Neither: ask for the approval, or hand the steps to the owner
   (`R-homenet-handoff`). The hard core is never covered by a standing entry (`R-homenet-never`).
3. **Read the current state.** Start one `homenet-reader` for the network side: is the address free, does the name
   exist already, which segment fits. It returns what it found as text.
4. **Network side.** One `homenet-writer` per assignment: reserve the address for the device and add the DNS name, one
   name for the service, and the configuration uses the name (`R-homenet-names`). The writer follows its order and
   integration rules (`homenet-writer`) and ends with the cross-check request.
5. **Integration, only if `homenet-home-assistant` is `yes`.** A separate assignment to the writer, explicit about the
   integration, under the same rules. A name or id that already has consumers goes through `R-homenet-rename` first.
6. **Cross-check.** A `homenet-reader` reads the result over its own way, never over the writer's: reservation, DNS
   answer, the device reachable under its name, the integration present with the expected entities. It returns a
   table of what it expected against what it found. A write counts as done only once this reader confirmed it; a
   difference goes back to the writer.
7. **Docs.** The orchestrator adds the device to the area file under `docs/project/homenet/` (name, area, model,
   firmware, network, protocol, purpose, data as of) and, if the naming scheme or a DNS name is new, to the places
   where those live. Add a journal line with what was changed and where the backup is.
8. **Report to the owner:** what was changed, the way back, and whatever remains for them (a physical step, a pairing
   button, a login in a browser).

Done when the reader confirmed the network side and, if used, the integration, the docs entry exists with a current
"data as of" line, the backup location and the way back are in the journal, and no step was taken that the table or a
dated approval did not cover.
