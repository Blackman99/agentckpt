(function(){
  const lines = [
    {html:'<span class="t-prompt">$</span> <span class="t-cmd">agentckpt init</span>'},
    {html:'<span class="t-dim">Initialized agentckpt store at .agentckpt/</span>'},
    {html:'<span class="t-prompt">$</span> <span class="t-cmd">agentckpt snap -m "before agent"</span>'},
    {html:'a1b2c3d  2026-10-09T03:00:00+08:00  12 files  before agent'},
    {html:'<span class="t-dim"># agent rewrites hello.txt and deletes utils.py …</span>'},
    {html:'<span class="t-prompt">$</span> <span class="t-cmd">agentckpt restore a1b2c3d --force</span>'},
    {html:'Restored 12 file(s) from a1b2c3d'},
    {html:'  + hello.txt'},
    {html:'  + src/utils.py'},
    {html:'<span class="t-ok">✓ working tree restored — real git HEAD untouched</span>'},
  ];
  const body = document.getElementById('term-body');
  if(!body) return;
  let i=0;
  function tick(){
    if(i>=lines.length) return;
    body.innerHTML += (i? '\n':'') + lines[i].html;
    i++;
    setTimeout(tick, 420);
  }
  tick();
  document.getElementById('replay')?.addEventListener('click', ()=>{ i=0; body.innerHTML=''; tick(); });
})();
