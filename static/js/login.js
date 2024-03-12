const numBars = 50;
const background = document.getElementById('background');
const activationDistance = 200; 
const maxHeight = 400; 
const colorBrightness = 100; 

for (let i = 0; i < numBars; i++) {
    let bar = document.createElement('div');
    bar.classList.add('bar');
    bar.style.height = `${Math.random() * 100}px`;
    bar.style.left = `${i / numBars * 100}%`;
    background.appendChild(bar);
}

document.addEventListener('mousemove', function(e) {
    const bars = document.querySelectorAll('.bar');
    bars.forEach(function(bar, index) {
        const dx = e.clientX - bar.getBoundingClientRect().left;
        const dy = e.clientY - bar.getBoundingClientRect().top - activationDistance; 
        const distance = Math.sqrt(dx * dx + dy * dy);
        let height = Math.max(maxHeight - distance / 2, 10); 
        height = Math.min(height, maxHeight); 
        bar.style.height = `${height}px`;
        
        const blueIntensity = Math.min(255, colorBrightness + Math.floor((height / maxHeight) * (255 - colorBrightness)));
        bar.style.backgroundColor = `rgb(0, ${blueIntensity}, 255)`;
    });
});