import React from 'react';
import { cn } from '../../lib/utils';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'highlight' | 'interactive';
}

const variantClasses: Record<NonNullable<CardProps['variant']>, string> = {
  default: 'surface-card',
  highlight: 'surface-card ring-1 ring-blue-200 dark:ring-blue-900',
  interactive: 'surface-card transition-shadow duration-200 hover:shadow-md',
};

export const Card: React.FC<CardProps> = ({ variant = 'default', className, ...props }) => {
  return <div className={cn(variantClasses[variant], className)} {...props} />;
};

export default Card;
