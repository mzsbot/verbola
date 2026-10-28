async function loadVisitorCount() {
    try {
        const response = await fetch('https://countapi.mileshilliard.com/api/v1/hit/verbola_casa_visitas');
        const data = await response.json();
        if (data && data.value !== undefined) {
            const countNum = parseInt(data.value, 10);
            document.getElementById('visitor-count').textContent = isNaN(countNum) ? data.value : countNum.toLocaleString('pt-PT');
        } else {
            document.getElementById('visitor-count').textContent = '1';
        }
    } catch (error) {
        document.getElementById('visitor-count').textContent = '1';
    }
}

loadVisitorCount();
