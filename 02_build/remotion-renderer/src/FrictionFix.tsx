/**
 * FrictionFix — Vertical short-form video (TikTok/Reels/Shorts)
 * 13 seconds, punchy, scroll-stopping.
 * Parametric: same template, different data, VARK-adapted.
 */
import React from 'react';
import {
  AbsoluteFill, useCurrentFrame, useVideoConfig,
  spring, interpolate, Sequence
} from 'remotion';

type VarkStyle = 'visual' | 'auditory' | 'read_write' | 'kinesthetic';
type GrowthStage = 'seed' | 'sprout' | 'grow' | 'scale' | 'accelerate';

interface FrictionFixProps {
  headline: string;
  script: string;
  varkStyle: VarkStyle;
  growthStage: GrowthStage;
  brandColor: string;
}

const VARK_FONTS: Record<VarkStyle, { size: number; weight: number }> = {
  visual: { size: 72, weight: 900 },
  auditory: { size: 60, weight: 700 },
  read_write: { size: 56, weight: 600 },
  kinesthetic: { size: 64, weight: 800 },
};

const STAGE_COLORS: Record<GrowthStage, string> = {
  seed: '#FF6B6B',
  sprout: '#4ECDC4',
  grow: '#45B7D1',
  scale: '#96CEB4',
  accelerate: '#FFEAA7',
};

export const FrictionFix: React.FC<FrictionFixProps> = ({
  headline, script, varkStyle, growthStage, brandColor
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const font = VARK_FONTS[varkStyle];
  const stageColor = STAGE_COLORS[growthStage];

  const headlineSpring = spring({ frame, fps, config: { damping: 12 } });
  const headlineY = interpolate(headlineSpring, [0, 1], [100, 0]);
  const headlineOpacity = interpolate(headlineSpring, [0, 1], [0, 1]);

  const scriptLines = script.split('\n').filter(Boolean);

  return (
    <AbsoluteFill style={{ backgroundColor: '#0a0a0a' }}>
      {/* Background gradient pulse */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
        background: `radial-gradient(circle at 50% 30%, ${brandColor}22, transparent 70%)`,
        opacity: interpolate(frame, [0, fps * 2], [0, 0.8], { extrapolateRight: 'clamp' }),
      }} />

      {/* Headline — HOOK (0-3s) */}
      <Sequence from={0} durationInFrames={fps * 4}>
        <div style={{
          position: 'absolute', top: '15%', left: '8%', right: '8%',
          transform: `translateY(${headlineY}px)`,
          opacity: headlineOpacity,
        }}>
          <h1 style={{
            color: '#ffffff', fontSize: font.size, fontWeight: font.weight,
            lineHeight: 1.1, margin: 0, fontFamily: 'Inter, system-ui, sans-serif',
          }}>
            {headline}
          </h1>
          <div style={{
            width: 80, height: 4, backgroundColor: brandColor,
            marginTop: 20, borderRadius: 2,
          }} />
        </div>
      </Sequence>

      {/* Script lines — staggered reveal */}
      {scriptLines.map((line, i) => {
        const startFrame = fps * 3 + i * fps * 2;
        const lineSpring = spring({
          frame: frame - startFrame, fps,
          config: { damping: 15, stiffness: 100 },
        });
        const lineOpacity = interpolate(
          lineSpring, [0, 1], [0, 1], { extrapolateLeft: 'clamp' }
        );
        const lineX = interpolate(
          lineSpring, [0, 1], [50, 0], { extrapolateLeft: 'clamp' }
        );

        return (
          <Sequence key={i} from={startFrame} durationInFrames={fps * 3}>
            <div style={{
              position: 'absolute',
              top: `${35 + i * 12}%`,
              left: '8%', right: '8%',
              opacity: lineOpacity,
              transform: `translateX(${lineX}px)`,
            }}>
              <p style={{
                color: '#e0e0e0', fontSize: font.size * 0.55,
                fontWeight: 400, lineHeight: 1.4, margin: 0,
                fontFamily: 'Inter, system-ui, sans-serif',
              }}>
                {line}
              </p>
            </div>
          </Sequence>
        );
      })}

      {/* Bottom bar — growth stage indicator */}
      <div style={{
        position: 'absolute', bottom: 40, left: '8%', right: '8%',
        display: 'flex', alignItems: 'center', gap: 12,
        opacity: interpolate(frame, [fps * 10, fps * 11], [0, 1],
          { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }),
      }}>
        <div style={{
          width: 12, height: 12, borderRadius: '50%',
          backgroundColor: stageColor,
        }} />
        <span style={{
          color: stageColor, fontSize: 18, fontWeight: 600,
          fontFamily: 'Inter, system-ui, sans-serif',
          textTransform: 'uppercase', letterSpacing: 2,
        }}>
          {growthStage} stage
        </span>
      </div>
    </AbsoluteFill>
  );
};
