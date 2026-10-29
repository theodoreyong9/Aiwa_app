// From a storyboard (the scenes of a film, each with the tool that makes it) to the list of shots to produce, with, for each shot made elsewhere, what to ask for
// and where to put the file, and to the clips.json that `video-kit assemble --clips` reads. It makes nothing: it writes down what each shot needs, so that nothing is forgotten
// and nothing is claimed that was not made.
//
// storyboard.json: { "title": "...", "format": "16:9", "scenes": [ { "id": "glasses", "seconds": 6, "tool": "html|blender|footage|generated", "line": "the voice line or card",
//                     "brief": "what we see", "camera": "slow dolly in", "licence": "for a footage: where it comes from and under which licence" } ] }
// tools: html (the cinematic engine, always available) · blender (3D made here, shots/blender) · footage (a real footage with our elements over it, tracked) ·
//        generated (a video made by a generator the user has: the prompt is written here, the file comes back from the user)
export const TOOLS = ['html', 'blender', 'footage', 'generated'];

export function buildShotlist(story, { clipsDir = 'aiwa-videos/clips', fps = 30 } = {}) {
  const scenes = story.scenes || [];
  if (!scenes.length) throw new Error('the storyboard has no scene');
  let at = 0;
  const rows = [], clips = [], problems = [];
  for (const s of scenes) {
    const tool = s.tool || 'html';
    if (!TOOLS.includes(tool)) problems.push(`${s.id}: unknown tool "${tool}" (${TOOLS.join(', ')})`);
    if (!(s.seconds > 0)) problems.push(`${s.id}: no duration`);
    if (tool === 'footage' && !s.licence) problems.push(`${s.id}: a footage needs its source and its licence (and the right to the image of the people in it)`);
    const start = Math.round(at * 100) / 100, end = Math.round((at + s.seconds) * 100) / 100;
    rows.push({ ...s, tool, start, end });
    if (tool !== 'html') clips.push({ shot: s.id, file: tool === 'blender' ? `${clipsDir}/${s.id}/%05d.png` : `${clipsDir}/${s.id}.mp4`, start, end, fps: tool === 'blender' ? fps : undefined, fit: 'cover', fade: 0.25 });
    at = end;
  }
  const fmt = story.format || '16:9';
  const lines = [`# Shots of « ${story.title || 'the film'} » (${fmt}, ${at.toFixed(1)} s)`, '', '| # | id | from | to | tool | what we see | line |', '|---|---|---|---|---|---|---|'];
  rows.forEach((r, i) => lines.push(`| ${i + 1} | ${r.id} | ${r.start} | ${r.end} | ${r.tool} | ${r.brief || ''} | ${r.line || ''} |`));
  const made = rows.filter((r) => r.tool === 'generated');
  if (made.length) {
    lines.push('', '## To ask a video generator for (the user\'s account: nothing is generated here)', '');
    for (const r of made) {
      lines.push(`### ${r.id} — ${r.seconds} s, ${fmt}`, '',
        `Prompt: ${r.brief}. ${r.camera ? `Camera: ${r.camera}.` : ''} Cinematic lighting, shallow depth of field, ${fmt} frame, no text, no logo, no watermark, no recognisable real person.`,
        `Put the file at \`${clipsDir}/${r.id}.mp4\`. It is a made-up picture: it is labelled as an illustration in the film.`, '');
    }
  }
  const real = rows.filter((r) => r.tool === 'footage');
  if (real.length) {
    lines.push('', '## Real footage', '');
    for (const r of real) lines.push(`- **${r.id}**: ${r.licence}. Track what the elements follow with \`track.py\`, render them with \`render --transparent\`, lay them with \`--clips\`.`);
  }
  if (problems.length) lines.push('', '## To fix before rendering', '', ...problems.map((p) => `- ${p}`));
  return { markdown: lines.join('\n') + '\n', clips, total: at, problems };
}
