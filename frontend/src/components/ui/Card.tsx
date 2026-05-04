import React from 'react';
import { cn } from '../../lib/utils';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'highlight' | 'interactive';
}

const variantClasses: Record<NonNullable<CardProps['variant']>, string> = {
  default: 'bg-white rounded-2xl border border-gray-100 shadow-sm',
  highlight: 'bg-white rounded-2xl border-2 shadow-lg',
  interactive: 'bg-white rounded-2xl border border-gray-100 shadow-sm transition-all duration-200 hover:shadow-lg',
};

export const Card: React.FC<CardProps> = ({ variant = 'default', className, ...props }) => {
  return <div className={cn(variantClasses[variant], className)} {...props} />;
};

export default Card;
