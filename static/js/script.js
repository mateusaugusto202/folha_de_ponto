async function fetchJSON(url, opts){ 
  const r = await fetch(url, opts);
  return r.json();
}

async function carregarFuncionarios(){
  const lista = await fetchJSON("/api/funcionarios");
  const sel = document.getElementById("funcSel");
  sel.innerHTML = "<option value=''>-- escolha --</option>";
  lista.forEach(f=>{
    const o = document.createElement("option");
    o.value = f.id; o.text = f.nome + (f.cpf?(" - "+f.cpf):"");
    sel.appendChild(o);
  });
}

document.getElementById("btnCriar").addEventListener("click", async ()=>{
  const nome = document.getElementById("nomeNovo").value.trim();
  const cpf = document.getElementById("cpfNovo").value.trim();
  if(!nome) return alert("Digite o nome");
  await fetchJSON("/api/funcionarios", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({nome, cpf})});
  document.getElementById("nomeNovo").value=""; document.getElementById("cpfNovo").value="";
  carregarFuncionarios();
});

document.querySelectorAll(".ponto").forEach(btn=>{
  btn.addEventListener("click", async (e)=>{
    const sel = document.getElementById("funcSel");
    const id = sel.value;
    if(!id) return alert("Escolha um funcionário");
    const acao = e.target.getAttribute("data-acao");
    const res = await fetchJSON("/api/ponto", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({funcionario_id: id, acao})});
    if(res.error) return alert(res.error);
    document.getElementById("status").innerText = "Registrado: " + acao;
    await carregarHoje(id);
    await carregarHistorico(id);
  });
});

async function carregarHoje(id){
  const hist = await fetchJSON("/api/historico/" + id + "?dias=1");
  const hoje = hist[0];
  const el = document.getElementById("horasHoje");
  if(!hoje || !hoje.horas_trabalhadas){
    el.innerText = "-";
    el.className = "neutral";
    return;
  }
  el.innerText = hoje.horas_trabalhadas + " h";
  const v = parseFloat(hoje.horas_trabalhadas);
  if(v === 0) el.className = "neutral";
  else if(v < 4) el.className = "bad";
  else el.className = "good";
}

async function carregarHistorico(id){
  const hist = await fetchJSON("/api/historico/" + id + "?dias=30");
  const tbody = document.getElementById("tbody");
  tbody.innerHTML = "";
  hist.forEach(r=>{
    const tr = document.createElement("tr");
    const d = new Date(r.data);
    tr.innerHTML = `
      <td>${d.toLocaleDateString()}</td>
      <td>${r.entrada||""}</td>
      <td>${r.inicio_almoco||""}</td>
      <td>${r.fim_almoco||""}</td>
      <td>${r.saida||""}</td>
      <td>${r.horas_trabalhadas||""}</td>
    `;
    tbody.appendChild(tr);
  });
}

async function init(){
  await carregarFuncionarios();
  document.getElementById("funcSel").addEventListener("change", async (e)=>{
    const id = e.target.value;
    if(id) { carregarHistorico(id); carregarHoje(id); }
    else { document.getElementById("tbody").innerHTML=""; document.getElementById("horasHoje").innerText="-"; }
  });
}

init();
