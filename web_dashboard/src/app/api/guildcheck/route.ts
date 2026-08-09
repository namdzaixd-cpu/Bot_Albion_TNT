import { NextResponse } from "next/server";

const REGION_BASE: Record<string, string> = {
  Asia: "https://gameinfo-sgp.albiononline.com/api/gameinfo",
  Americas: "https://gameinfo.albiononline.com/api/gameinfo",
  Europe: "https://gameinfo-ams.albiononline.com/api/gameinfo",
};

// Guild TNC trên Albion (lấy từ /search). Có thể đưa vào env sau.
const TNC_GUILD_ID = "8MZNHa-7SPW5LMWvqIV81g";
const TNC_REGION = "Asia";

async function fetchGuild() {
  const base = REGION_BASE[TNC_REGION];
  const [g, gd] = await Promise.all([
    fetch(`${base}/guilds/${TNC_GUILD_ID}`, { next: { revalidate: 120 }, headers: { "User-Agent": "tnc-dashboard" } }),
    fetch(`${base}/guilds/${TNC_GUILD_ID}/data`, { next: { revalidate: 120 }, headers: { "User-Agent": "tnc-dashboard" } }),
  ]);
  if (!g.ok || !gd.ok) throw new Error("Albion API lỗi");
  const guild = await g.json();
  const data = await gd.json();

  const members = (guild.Members || []).map((m: { Name?: string; Id?: string; KillFame?: number }) => ({
    name: m.Name, id: m.Id, killFame: m.KillFame ?? 0,
  }));
  members.sort((a: any, b: any) => (b.killFame || 0) - (a.killFame || 0));

  return {
    name: guild.Name,
    founder: guild.FounderName,
    founded: guild.Founded,
    alliance: guild.AllianceName && guild.AllianceName !== "None" ? guild.AllianceName : null,
    killFame: guild.killFame ?? 0,
    deathFame: guild.DeathFame ?? 0,
    attacksWon: guild.AttacksWon ?? 0,
    defensesWon: guild.DefensesWon ?? 0,
    stats: data.overall ?? {},
    memberCount: data.basic?.memberCount ?? members.length,
    topPlayers: (data.topPlayers || []).slice(0, 10).map((p: any) => ({
      name: p.Name, killFame: p.KillFame ?? 0, deathFame: p.DeathFame ?? 0,
    })),
    members,
    updated_at: new Date().toISOString(),
  };
}

export async function GET() {
  try {
    const guild = await fetchGuild();
    return NextResponse.json(guild);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "Lỗi";
    return NextResponse.json({ error: msg }, { status: 502 });
  }
}
