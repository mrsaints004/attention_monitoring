import type { ReadingData } from "./api";
export function utcDate(timestamp: string) { return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(timestamp) ? timestamp : `${timestamp}Z`); }
export function historyTimeline(readings: ReadingData[], classAverage = false) {
  const chronological = [...readings].sort((a,b) => utcDate(a.timestamp).getTime() - utcDate(b.timestamp).getTime());
  if (!classAverage) return chronological.map(r => ({ time: utcDate(r.timestamp).toLocaleTimeString(), attention: r.quality_flag === "normal" ? r.attention_index : null }));
  const buckets = new Map<number, Map<string, number[]>>();
  for (const r of chronological) {
    const time = Math.floor(utcDate(r.timestamp).getTime() / 1000) * 1000;
    if (!buckets.has(time)) buckets.set(time, new Map());
    if (r.quality_flag !== "normal" || r.attention_index === null) continue;
    const students = buckets.get(time)!;
    const values = students.get(r.student_id) || []; values.push(r.attention_index); students.set(r.student_id, values);
  }
  return [...buckets].map(([time, students]) => {
    const means = [...students.values()].map(values => values.reduce((a,b) => a+b,0) / values.length);
    return { time: new Date(time).toLocaleTimeString(), attention: means.length ? means.reduce((a,b) => a+b,0) / means.length : null };
  });
}
