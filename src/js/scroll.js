async function firstGameScroll()
{
    const games = await fetch(`/data/jogos.json?t=${new Date().getTime()}`)
        .then((response) => response.json());

    const now       = new Date();
    const nowInMins = (now.getHours() * 60) + now.getMinutes();

    const game = games.find(({ time, is_today }) => {
        if(!is_today || !time) return false;

        const [gameH, gameM] = time.split(':').map(Number);

        const gameTimeInMins = (gameH * 60) + gameM;
        const tolerance      = 115;

        return nowInMins <= gameTimeInMins || nowInMins <= (gameTimeInMins + tolerance);
    });

    if(game !== undefined)
    {
        const gameEl = document.getElementById(game?.id);
        const topBar = document.getElementById("top-bar");

        let yScrollTo = gameEl.offsetTop - topBar.clientHeight;
        console.log(gameEl.scrollHeight + topBar.clientHeight);
        window.scrollTo(0, yScrollTo);
    }
}

firstGameScroll();
