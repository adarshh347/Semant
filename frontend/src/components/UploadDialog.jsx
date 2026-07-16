// Shell-level upload surface. Upload used to be a form pinned above the archive;
// now it's an action (⌘K → "Upload an image", or the Archive's Upload button)
// that opens this Radix dialog. On success it broadcasts `semant:posts-changed`
// so the archive refreshes, and invalidates the posts cache.
import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Dialog, DialogContent, useToast } from './ui';
import UploadForm from './UploadForm';

export default function UploadDialog() {
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();
  const { toast } = useToast();

  useEffect(() => {
    const onOpen = () => setOpen(true);
    window.addEventListener('semant:open-upload', onOpen);
    return () => window.removeEventListener('semant:open-upload', onOpen);
  }, []);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent
        title="Add to the archive"
        description="Upload an image to read and write from."
        size="md"
      >
        <UploadForm
          onUploadSuccess={() => {
            queryClient.invalidateQueries({ queryKey: ['posts'] });
            window.dispatchEvent(new CustomEvent('semant:posts-changed'));
            toast({
              variant: 'success',
              title: 'Image added',
              description: 'It’s in the archive.',
            });
            setOpen(false);
          }}
        />
      </DialogContent>
    </Dialog>
  );
}
