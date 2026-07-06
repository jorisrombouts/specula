import { type Tweaks } from "@/lib/tweaks-init";
import { bffFetch } from "@/lib/api/bff";

export async function getTweaks(): Promise<Tweaks> {
  return bffFetch<Tweaks>("/tweaks");
}

export async function putTweaks(tweaks: Tweaks): Promise<Tweaks> {
  return bffFetch<Tweaks>("/tweaks", {
    method: "PUT",
    body: JSON.stringify(tweaks),
  });
}
