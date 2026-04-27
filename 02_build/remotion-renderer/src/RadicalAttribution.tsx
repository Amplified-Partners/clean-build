/**
 * RadicalAttribution — Landscape video (LinkedIn/YouTube)
 * 10 seconds, data-driven, shows the numbers.
 * Pure radical transparency: the data speaks for itself.
 */
import React from 'react';
import {
  AbsoluteFill, useCurrentFrame, useVideoConfig,
  spring, interpolate, Sequence
} from 'remotion';

type VarkStyle = 'visual' | 'auditory' | 'read_write' | 'kinesthetic';
type GrowthStage = 'seed' | 'sprout' | 'grow' | 'scale' | 'accelerate';

interface RadicalAttributionProps {
  headline: string;
  dataPoints: string[];
  varkStyle: VarkStyle;
  growthStage: GrowthStage;
  brandColor: string;
}

export const RadicalAttribution: React.FC<RadicalAttributionProps> = ({
  headline, dataPoints, varkStyle, growthStage, brandColor
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  return (
    <AbsoluteFill style={{ backgroundColor: '#0a0a0a' }}>
      {/* Grid background */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
        backgroundImage: `
          linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
          linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)
        `,
        backgroundSize: '40px 40px',
      }} />

      {/* Headline */}
      <Sequence from={0} durationInFrames={fps * 10}>
        <div style={{
          position: 'absolute', top: '10%', left: '5%', right: '50%',
          opacity: interpolate(
            spring({ frame, fps, config: { damping: 12 } }),
            [0, 1], [0, 1]
          ),
        }}>
          <h1 style={{
            color: '#ffffff', fontSize: 48, fontWeight: 800,
            lineHeight: 1.15, margin: 0,
            fontFamily: 'Inter, system-ui, sans-serif',
          }}>
            {headline}
          </h1>
        </div>
      </Sequence>

      {/* Data points — right side, staggered */}
      {dataPoints.map((point, i) => {
        const startFrame = fps * 1.5 + i * fps * 1.5;
        const pointSpring = spring({
          frame: frame - startFrame, fps,
          config: { damping: 14, stiffness: 80 },
        });

        return (
          <Sequence key={i} from={Math.round(startFrame)} durationInFrames={fps * 8}>
            <div style={{
              position: 'absolute',
              top: `${15 + i * 18}%`,
              right: '5%',
              width: '42%',
              opacity: interpolate(pointSpring, [0, 1], [0, 1],
                { extrapolateLeft: 'clamp' }),
              transform: `translateX(${interpolate(pointSpring, [0, 1], [80, 0],
                { extrapolateLeft: 'clamp' })}px)`,
            }}>
              <div style={{
                backgroundColor: `${brandColor}15`,
                border: `1px solid ${brandColor}40`,
                borderRadius: 12, padding: '20px 28px',
              }}>
                <p style={{
                  color: brandColor, fontSize: 36, fontWeight: 700,
                  margin: 0, fontFamily: 'Inter, system-ui, sans-serif',
                }}>
                  {point}
                </p>
              </div>
            </div>
          </Sequence>
        );
      })}

      {/* Amplified Partners watermark */}
      <div style={{
        position: 'absolute', bottom: 20, right: 24,
        opacity: 0.3,
      }}>
        <span style={{
          color: '#ffffff', fontSize: 14, fontWeight: 400,
          fontFamily: 'Inter, system-ui, sans-serif',
          letterSpacing: 1,
        }}>
          amplifiedpartners.ai
        </span>
      </div>
    </AbsoluteFill>
  );
};
