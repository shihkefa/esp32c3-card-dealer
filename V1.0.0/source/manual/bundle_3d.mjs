// Bundle pinned upstream Three.js and OrbitControls for a single offline HTML.
// Download the npm tarballs noted in README_重建.txt to .build/web3d first.
import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
const root=fileURLToPath(new URL('../../',import.meta.url));
const build=path.join(root,'.build/web3d');
const three=path.join(build,'three/package');
const wasm=path.join(build,'esbuild-wasm/package');
const require=createRequire(import.meta.url);
const esbuild=require(path.join(wasm,'lib/main.js'));
const out=path.join(root,'manual/vendor');await fs.mkdir(out,{recursive:true});
const entry=path.join(build,'entry.mjs');
await fs.writeFile(entry,`import * as THREE from ${JSON.stringify(path.join(three,'build/three.module.js').replaceAll('\\','/'))};\nimport {OrbitControls} from ${JSON.stringify(path.join(three,'examples/jsm/controls/OrbitControls.js').replaceAll('\\','/'))};\nwindow.THREE=THREE;window.OrbitControls=OrbitControls;\n`);
const target=path.join(out,'three-orbit.min.js');
await esbuild.build({entryPoints:[entry],bundle:true,format:'iife',platform:'browser',target:['es2020'],minify:true,
  alias:{three:path.join(three,'build/three.module.js')},outfile:target,legalComments:'eof'});
await fs.copyFile(path.join(three,'LICENSE'),path.join(out,'THREE_LICENSE.txt'));
const sha=p=>fs.readFile(p).then(b=>createHash('sha256').update(b).digest('hex'));
await fs.writeFile(path.join(out,'vendor_manifest.json'),JSON.stringify({
  three:{version:'0.180.0',source:'https://registry.npmjs.org/three/-/three-0.180.0.tgz',license:'MIT',tar_sha256:await sha(path.join(build,'three.tgz'))},
  buildTool:{name:'esbuild-wasm',version:'0.25.10',source:'https://registry.npmjs.org/esbuild-wasm/-/esbuild-wasm-0.25.10.tgz',temporary:true},
  bundle:{file:'three-orbit.min.js',sha256:await sha(target)},
  runtimeNetworkRequired:false
},null,2)+'\n');
console.log(JSON.stringify({bundle:target,bytes:(await fs.stat(target)).size}));
esbuild.stop();
