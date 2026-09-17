'use client';

import React, { useEffect, useRef } from 'react';

export default function InteractiveBackground() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId: number;
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    const handleResize = () => {
      if (!canvas) return;
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };
    window.addEventListener('resize', handleResize);

    // Mouse Tracking State
    const mouse = {
      x: width / 2,
      y: height / 2,
      targetX: width / 2,
      targetY: height / 2,
      radius: 200,
    };

    const handleMouseMove = (e: MouseEvent) => {
      mouse.targetX = e.clientX;
      mouse.targetY = e.clientY;
    };
    window.addEventListener('mousemove', handleMouseMove);

    // Particle System (Includes both White & Teal Dust Particles)
    const particleCount = Math.min(Math.floor(width / 5), 220);
    const particles = Array.from({ length: particleCount }, () => {
      const isWhite = Math.random() > 0.45; // ~55% white, 45% teal
      return {
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.4,
        vy: (Math.random() - 0.5) * 0.4,
        radius: Math.random() * 2.2 + 0.8,
        alpha: isWhite ? Math.random() * 0.35 + 0.15 : Math.random() * 0.45 + 0.15,
        color: isWhite ? '255, 255, 255' : '45, 212, 191',
      };
    });

    // Continuous Watermark Track States
    let offset1 = 0;
    let offset2 = 0;

    const angle = -0.42; // ~-24 degree diagonal tilt
    const speed1 = 1.2;  // Flow speed for top track
    const speed2 = -1.0; // Flow speed for bottom track

    // Render Infinite Tiled Text Line
    const drawContinuousTrack = (
      textUnit: string,
      yPos: number,
      currentOffset: number,
      fillColor: string,
      strokeColor: string
    ) => {
      ctx.save();
      ctx.translate(width / 2, height / 2);
      ctx.rotate(angle);

      ctx.font = '800 64px Inter, system-ui, sans-serif';
      ctx.fillStyle = fillColor;
      ctx.strokeStyle = strokeColor;
      ctx.lineWidth = 1.5;

      const unitWidth = ctx.measureText(textUnit).width;
      const startX = -width * 1.5 + (currentOffset % unitWidth);

      for (let x = startX; x < width * 1.5; x += unitWidth) {
        ctx.fillText(textUnit, x, yPos);
        ctx.strokeText(textUnit, x, yPos);
      }

      ctx.restore();
    };

    // Main Animation Loop
    const render = () => {
      mouse.x += (mouse.targetX - mouse.x) * 0.05;
      mouse.y += (mouse.targetY - mouse.y) * 0.05;

      ctx.clearRect(0, 0, width, height);

      // Increment Marquee Offsets
      offset1 += speed1;
      offset2 += speed2;

      // 1. DRAW CONTINUOUS DIAGONAL WATERMARKS
      drawContinuousTrack(
        'ARHAM MAHMOOD   •   ',
        -70,
        offset1,
        'rgba(20, 184, 166, 0.07)',
        'rgba(45, 212, 191, 0.22)'
      );

      drawContinuousTrack(
        'RAG PROJECT DEMO  •   ',
        90,
        offset2,
        'rgba(20, 184, 166, 0.06)',
        'rgba(45, 212, 191, 0.18)'
      );

      // 2. DRAW INTERACTIVE DUST PARTICLES (White + Teal)
      particles.forEach((p) => {
        p.x += p.vx;
        p.y += p.vy;

        if (p.x < 0) p.x = width;
        if (p.x > width) p.x = 0;
        if (p.y < 0) p.y = height;
        if (p.y > height) p.y = 0;

        const dx = mouse.x - p.x;
        const dy = mouse.y - p.y;
        const dist = Math.sqrt(dx * dx + dy * dy);

        let currentAlpha = p.alpha;
        let currentRadius = p.radius;

        if (dist < mouse.radius) {
          const force = 1 - dist / mouse.radius;
          p.x -= (dx / dist) * force * 1.5;
          p.y -= (dy / dist) * force * 1.5;
          currentAlpha = Math.min(0.9, p.alpha + force * 0.4);
          currentRadius = p.radius + force * 1.8;
        }

        ctx.beginPath();
        ctx.arc(p.x, p.y, currentRadius, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${p.color}, ${currentAlpha})`;
        ctx.fill();
      });

      // 3. DRAW CONNECTING DUST LINKS
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < 90) {
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.strokeStyle = `rgba(255, 255, 255, ${0.05 * (1 - dist / 90)})`;
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        }
      }

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('mousemove', handleMouseMove);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none z-0 bg-[#0A0F0D]"
    />
  );
}