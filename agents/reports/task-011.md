# Report — task-011

## Scope done
Selesai dan terdorong ke `dev` sebagai NEXONE `c762e41`.

- N1 kolom ExternalSource/ExternalRef + unique index gabungan
- N2 dispatcher dipersempit ke sprint-linked ATAU externally linked
- N3 updated_since + cursor pada GET tasks
- N4 keputusan: envelope NEXONE tidak diubah, SUPPORT yang beradaptasi

Verifikasi: `go build`, `go vet`, `go test ./...` hijau di dev setelah merge.

## Files changed
Lihat commit yang disebut di atas.

## Not done / blocked
Tidak ada. Sisa pekerjaan yang berkaitan dilacak terpisah:
task-022 (SUPPORT pakai updated_since), task-023 (mapping title/description/assignee),
task-024 (verifikasi end-to-end ke API hidup).

## Suggested next task
task-024 — tidak ada satu pun jalur ini yang pernah diuji terhadap NEXONE yang hidup.
