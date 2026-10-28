let query = '';

const container = document.getElementById('games-container');
const input     = document.getElementById('search-input');
const clearBtn  = document.getElementById('search-clear');
const hint      = document.getElementById('search-hint');
const meta      = document.getElementById('search-meta');

const UNKNOWN_COMPETITION_ICON = '../assets/icons/competicoes/desconhecida.svg';

// Minúsculas e sem acentos: "milao" encontra "Milão"
const fold = s => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

const escapeHtml = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// Realça os termos pesquisados mantendo o texto original (com acentos)
function highlight(text, terms) {
    text = String(text ?? '');
    if (!terms.length) return escapeHtml(text);

    const chars  = [...text];
    const folded = chars.map(fold);
    const flat   = folded.join('');
    const owner  = []; // índice do caracter original para cada posição de `flat`
    folded.forEach((f, i) => { for (let k = 0; k < f.length; k++) owner.push(i); });

    const marked = new Array(chars.length).fill(false);
    terms.forEach(t => {
        let pos = flat.indexOf(t);
        while (pos !== -1) {
            for (let k = pos; k < pos + t.length; k++) marked[owner[k]] = true;
            pos = flat.indexOf(t, pos + t.length);
        }
    });

    let out  = '';
    let open = false;
    chars.forEach((c, i) => {
        if (marked[i] && !open) { out += '<mark>'; open = true; }
        if (!marked[i] && open) { out += '</mark>'; open = false; }
        out += escapeHtml(c);
    });
    return open ? out + '</mark>' : out;
}

function matchesGame(game, terms) {
    const haystack = fold([game.match, game.competition, ...(game.channels || []), game.date].join(' '));
    return terms.every(t => haystack.includes(t));
}

function checkIsLive(timeStr, isToday) {
    if (!isToday || !timeStr) return false;
    
    const now = new Date();
    const nowInMins = (now.getHours() * 60) + now.getMinutes();
    const [gameH, gameM] = timeStr.split(':').map(Number);
    if (isNaN(gameH) || isNaN(gameM)) return false;
    
    const gameTimeInMins = (gameH * 60) + gameM;
    const tolerance = 115;
    return nowInMins >= gameTimeInMins && nowInMins <= (gameTimeInMins + tolerance);
}

async function loadGames() {    
    try {
        const allGames = await fetch(`/data/jogos.json?t=${new Date().getTime()}`)
            .then((response) => response.json());
        const terms = fold(query).split(/\s+/).filter(Boolean);
        const games = terms.length ? allGames.filter(g => matchesGame(g, terms)) : allGames;

        clearBtn.classList.toggle('hidden', !query);
        hint.classList.toggle('sm:inline-block', !query);
        meta.classList.toggle('hidden', !terms.length);
        meta.textContent = `${games.length} de ${allGames.length} jogos`;
        
        if (allGames.length === 0) {
            container.innerHTML = '<div class="text-center text-zinc-500 mt-10">Nenhum evento agendado.</div>';
            return;
        }

        if (games.length === 0) {
            container.innerHTML = `
                <div class="text-center mt-10 space-y-2">
                    <div class="text-4xl opacity-30 grayscale">⚽</div>
                    <div class="text-zinc-400 text-sm">Nenhum jogo encontrado para <span class="text-zinc-100 font-semibold">“${escapeHtml(query.trim())}”</span></div>
                    <button type="button" onclick="setQuery('')" class="text-xs text-red-400 hover:text-red-300 font-semibold">Limpar pesquisa</button>
                </div>`;
            return;
        }

        container.innerHTML = games.map((game, index) => {
            const isLive = checkIsLive(game.time, game.is_today);
            
            // Alternância entre tons de cinzento neutro e elegante
            const bgClass = index % 2 === 0 ? 'bg-zinc-900/90' : 'bg-zinc-900/50';
            
            const liveStyles = isLive 
                ? 'border-l-4 border-l-red-500 border-t border-b border-r border-zinc-800 shadow-[inset_4px_0_0_0_rgba(239,68,68,1),0_0_15px_rgba(239,68,68,0.12)] bg-zinc-900' 
                : `border border-zinc-800/80 ${bgClass}`;

            // Ícone da competição; sem correspondência (ou imagem em falta) usa o genérico
            const competitionIcon = game.competition_icon ? `../${game.competition_icon}` : UNKNOWN_COMPETITION_ICON;
            const competitionIconHtml = `<img src="${competitionIcon}" onerror="this.onerror=null;this.src='${UNKNOWN_COMPETITION_ICON}'" alt="" title="${escapeHtml(game.competition || 'Competição desconhecida')}" class="h-10 w-10 sm:h-11 sm:w-11 shrink-0 rounded-md bg-zinc-800/80 p-1 object-contain" loading="lazy">`;

            const flagsHtml = game.flags && game.flags.length > 0 
                ? `<div class="flex gap-1 ml-2 opacity-90">${game.flags.map(f => `<img src="${f}" class="h-4 object-contain rounded-xs" loading="lazy">`).join('')}</div>` 
                : '';

            const channelsHtml = game.channels && game.channels.length > 0
                ? game.channels.map(c => `<span class="bg-zinc-800/80 text-zinc-300 border border-zinc-700/60 text-[11px] px-2 py-0.5 rounded uppercase tracking-wider font-semibold whitespace-nowrap">${highlight(c, terms)}</span>`).join('')
                : '<span class="text-zinc-600 text-xs font-semibold">N/D</span>';

            // Equipas clicáveis: pesquisa rápida pela equipa
            const teamButton = team => `<button type="button" data-team="${escapeHtml(team)}" class="team-chip cursor-pointer hover:text-white hover:underline underline-offset-2 decoration-zinc-500">${highlight(team, terms)}</button>`;
            const matchHtml  = game.match.split(' - ').map(t => t.trim()).filter(Boolean).map(teamButton).join(' - ');

            const todayTag = game.is_today 
                ? `<span class="text-red-400 font-bold ml-1 text-xs">hoje</span>` 
                : '';

            const watermark = '<div class="absolute top-1/2 -translate-y-1/2 -right-[75px] sm:-right-[85px] text-[130px] sm:text-[150px] opacity-[0.07] grayscale select-none pointer-events-none z-0">⚽</div>';

            return `
            <div class="relative overflow-hidden rounded-lg p-3 sm:p-4 ${liveStyles}">
                
                ${watermark}

                <!-- Conteúdo do Cartão -->
                <div class="game-grid relative z-10">
                    <div class="flex flex-col border-r border-zinc-800 pr-2">
                        <span class="text-sm font-semibold text-zinc-400 whitespace-nowrap">${highlight(game.date, terms)}</span>
                        <div class="flex items-baseline">
                            <span class="text-sm font-bold text-zinc-100">${game.time}</span>
                            ${todayTag}
                        </div>
                    </div>

                    <div class="flex items-center gap-2.5 sm:gap-3 pl-1 sm:pl-2 min-w-0">
                        ${competitionIconHtml}
                        <div class="flex flex-col justify-center min-w-0">
                            <div class="flex items-center">
                                <span class="text-[15px] font-bold text-zinc-100 truncate">${matchHtml}</span>
                                ${flagsHtml}
                            </div>
                            <span class="text-xs text-zinc-400 italic truncate mt-0.5">${highlight(game.competition, terms)}</span>
                        </div>
                    </div>

                    <div class="channels-col flex sm:flex-col lg:flex-row flex-wrap gap-1.5 justify-end items-end sm:items-center">
                        ${channelsHtml}
                    </div>
                </div>
            </div>
            `;
        }).join('');
    } catch (error) {
        container.innerHTML = '<div class="text-center text-red-400 mt-10 p-4 bg-red-950/20 border border-red-900/40 rounded-lg">Erro de ligação ao ficheiro JSON.</div>';
        console.log(error);
    }
}

function setQuery(value) {
    query       = value;
    input.value = value;

    history.replaceState(null, '', value ? `?q=${encodeURIComponent(value)}` : location.pathname);
    loadGames();
}

input.addEventListener('input', e => setQuery(e.target.value));
clearBtn.addEventListener('click', () => { setQuery(''); });

container.addEventListener('click', e => {
    const chip = e.target.closest('.team-chip');
    if (chip) setQuery(chip.dataset.team);
});

// "/" foca a pesquisa, "Esc" limpa
document.addEventListener('keydown', e => {
    if (e.key === '/' && document.activeElement !== input) {
        e.preventDefault();
        input.focus();
    } else if (e.key === 'Escape' && document.activeElement === input) {
        setQuery('');
        input.blur();
    }
});

loadGames();
setInterval(loadGames, 60000);
