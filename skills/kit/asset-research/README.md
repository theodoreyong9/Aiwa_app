# asset-research

A register of free (**CC0**) assets for the shots of a film: **3D models** (glTF), **HDRI lights** and **PBR textures**, from Poly Haven (about 520 models, 1000 HDRIs, 870 textures; everything it publishes is CC0, no credit asked, and it has a public API for programs). One line per asset in `catalog/assets.jsonl`: name, tags, categories, description, authors, size in mm, polycount, the biggest resolution, its page. The agent **searches** it, downloads **only what it keeps**, and **transforms** it in the shot (`video-kit/shots/blender/kit.py`): it is a base, never a finished scene.

```
node asset-research/src/cli.js search "un vieux fauteuil en bois" --kind=model --max-poly=50000
node asset-research/src/cli.js search "lumière d'un lever de soleil" --kind=hdri
node asset-research/src/cli.js fetch ph-ArmChair_01 assets/chair --res=2k      # the .gltf, its .bin and its textures
node asset-research/src/cli.js stats
```
Without the repository cloned: `AR_CATALOG_URL=https://raw.githubusercontent.com/theodoreyong9/Aiwa_app/main/skills/kit/asset-research/catalog/assets.jsonl`. The brief may be in French (the common words are carried over to the English tags).

## Where the files come from

`fetch` asks the Poly Haven API for the files of the asset, then downloads them. A session whose network cannot reach `api.polyhaven.com` or `dl.polyhaven.org` (the one that writes this could not) falls back on the copy in the release `assets` of this repository: one zip per asset, made **on request** by the workflow *Asset mirror* (`ids`, `res`), only for assets of the register. Nothing is stored here that nobody asked for.

## What is measured, what is not

All of it is the author's own description and numbers (tags, polycount, dimensions): nothing is measured here, and a model is not looked at before it is kept: the page of the asset (`page`) has its picture. If neither the source nor the copy can be reached, say so and make the shape in the shot (`kit.py` and the example `examples/product.py` make shapes from nothing).

Weekly sync: `.github/workflows/asset-catalog-sync.yml`. Tests: `npm test` in this folder.
